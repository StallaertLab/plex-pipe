"""Channel manifest: the complete inventory of input image files.

A manifest lists **every** input file together with the marker it contains and
the imaging round it was acquired in. It is either generated from file names
with a naming preset (e.g. ``celldive``) or written by the user as a CSV file.

The manifest is an inventory: it describes *what exists*, plus an optional
per-file ``use`` flag. Which channels are actually used is decided downstream
by the selection rules in
:mod:`plex_pipe.stages.roi_preparation.channel_scanner`, which are applied on
top of the ``use`` flag.

CSV format (header required; comma, semicolon or tab separated)::

    file,marker,round,use
    BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif,DAPI,1,
    BLCA-1_1.0.4_R000_Cy3_pH2AX-AF555_FINAL_AFR_F.ome.tif,pH2AX,1,no

* ``file``: file name in ``general.image_dir`` (no sub-folders).
* ``marker``: marker name used throughout the pipeline (it becomes the image
  layer name). One channel is kept per marker; to keep two rounds of the same
  marker, give them different marker names (e.g. ``CD45`` and ``CD45_1``).
* ``round``: optional non-negative integer; a blank cell or a missing column
  means round 1.
* ``use``: optional; a blank cell or a missing column means the file may be
  used. ``no`` / ``false`` / ``0`` removes the file before the selection rules
  run. See :data:`USE_TRUE` / :data:`USE_FALSE` for accepted values.

Any other columns are ignored, so the file can carry notes.
"""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROUND = 1
REQUIRED_COLUMNS = ("file", "marker")
OUTPUT_COLUMNS = ("file", "marker", "round", "use")

#: Accepted ``use`` values (case-insensitive). A blank cell means yes.
USE_TRUE = frozenset({"yes", "y", "true", "t", "1"})
USE_FALSE = frozenset({"no", "n", "false", "f", "0"})


class ManifestError(ValueError):
    """Raised when a channel manifest is malformed or ambiguous."""


@dataclass(frozen=True)
class ChannelRecord:
    """One input file: which marker it holds, in which round, and whether the
    user allows it to be used (``use=False`` removes it before selection)."""

    file: str
    marker: str
    round: int = DEFAULT_ROUND
    use: bool = True

    @property
    def channel(self) -> str:
        """Unique channel name, e.g. ``002_CD3``."""
        return f"{self.round:03d}_{self.marker}"


###################################################################
# Naming presets: file name -> (marker, round) or None if not recognised
###################################################################

# Cell DIVE: [Prefix]_[Round].0.4_R000_[Dye]_[Marker]-[Suffix]_....ome.tif
# A dye segment containing "DAPI" (any case) marks a DAPI image; otherwise the
# marker is the segment after the dye with its last "-suffix" removed. The
# trailing "_..." part is optional (e.g. "..._Cy3_CK7-01.ome.tif").
_CELLDIVE_DAPI = re.compile(
    r"^[^_]+_(?P<round>\d+)\.0\.4_R000_[^_]*(?i:dapi)[^_]*_.*\.tiff?$"
)
_CELLDIVE_MARKER = re.compile(
    r"^[^_]+_(?P<round>\d+)\.0\.4_R000_[^_]+_(?P<marker>[^_]+?)"
    r"(?:-[^-_]*)?(?:_.*)?(?:\.ome)?\.tiff?$"
)


def parse_celldive_name(fname: str) -> tuple[str, int] | None:
    """Parse a Cell DIVE file name into ``(marker, round)``.

    Args:
        fname: File name (not a path).

    Returns:
        ``(marker, round)``, or ``None`` if the name does not follow the
        Cell DIVE convention.
    """
    m = _CELLDIVE_DAPI.match(fname)
    if m:
        return "DAPI", int(m["round"])
    m = _CELLDIVE_MARKER.match(fname)
    if m:
        return m["marker"], int(m["round"])
    return None


#: Registered naming presets. Add a new platform by adding a parser here.
NAMING_PRESETS: dict[str, Callable[[str], tuple[str, int] | None]] = {
    "celldive": parse_celldive_name,
}

#: Preset used when none is named: in the config (``file_naming`` left out) and
#: when ``save_manifest`` / ``preview_channels`` build a manifest from file
#: names without ``preset=``.
DEFAULT_PRESET = "celldive"

#: Markers for which the earliest round is kept (all others keep the latest),
#: when ``channels.earliest_round_markers`` is not set in the config.
DEFAULT_EARLIEST_ROUND_MARKERS = ("DAPI",)


###################################################################
# Building, validating, reading and writing manifests
###################################################################


def build_manifest(
    files: Iterable[str], preset: str, strict: bool = True
) -> tuple[list[ChannelRecord], list[str]]:
    """Generate a manifest from file paths using a naming preset.

    Args:
        files: File paths (local or remote); only the base name is parsed and
            stored.
        preset: Name of a preset in :data:`NAMING_PRESETS`.
        strict: Raise if two files resolve to the same channel. Previews pass
            ``False`` to report duplicates instead of failing.

    Returns:
        ``(records, unmatched)``: records sorted by channel name, and the base
        names of files the preset did not recognise.

    Raises:
        ManifestError: If the preset is unknown, or (when ``strict``) two files
            resolve to the same channel.
    """
    try:
        parse = NAMING_PRESETS[preset]
    except KeyError:
        raise ManifestError(
            f"Unknown naming preset {preset!r}. Available: {sorted(NAMING_PRESETS)}"
        ) from None

    records, unmatched = [], []
    for path in files:
        name = _basename(path)
        parsed = parse(name)
        if parsed is None:
            unmatched.append(name)
        else:
            marker, rnd = parsed
            records.append(ChannelRecord(file=name, marker=marker, round=rnd))

    if strict:
        validate_records(records)
    return sorted(records, key=lambda r: r.channel), sorted(unmatched)


def duplicate_channels(records: Iterable[ChannelRecord]) -> dict[str, list[str]]:
    """Channels that come from more than one file.

    Returns:
        ``{channel: [file, file, ...]}`` for every ambiguous channel.
    """
    files_by_channel: dict[str, list[str]] = {}
    for r in records:
        files_by_channel.setdefault(r.channel, []).append(r.file)
    return {ch: fs for ch, fs in files_by_channel.items() if len(fs) > 1}


def validate_records(records: Iterable[ChannelRecord]) -> None:
    """Check that files and channel names are unique.

    Raises:
        ManifestError: Listing every duplicate found.
    """
    problems = []
    by_file: dict[str, ChannelRecord] = {}
    by_channel: dict[str, ChannelRecord] = {}
    for r in records:
        if r.file in by_file:
            problems.append(f"file {r.file!r} is listed more than once")
        by_file[r.file] = r
        if r.channel in by_channel:
            problems.append(
                f"channel {r.channel} (marker {r.marker!r}, round {r.round}) "
                f"comes from both {by_channel[r.channel].file!r} and {r.file!r}"
            )
        by_channel[r.channel] = r
    if problems:
        raise ManifestError(
            "Ambiguous channel manifest:\n  - " + "\n  - ".join(problems)
        )


def channel_marker(channel: str) -> str:
    """Marker part of a channel name: ``"002_CD45"`` -> ``"CD45"``.

    The name is split at the first ``_`` after the round number, so
    ``"002_CD45_1"`` gives ``"CD45_1"``. A name without a round prefix is
    returned unchanged.
    """
    prefix, sep, marker = channel.partition("_")
    return marker if sep and prefix.isdigit() else channel


def selection_rule_conflicts(
    include_channels: Iterable[str] = (),
    exclude_channels: Iterable[str] = (),
    use_markers: Iterable[str] = (),
    ignore_markers: Iterable[str] = (),
) -> list[str]:
    """Find selection settings that contradict each other.

    A setting cannot both ask for and reject the same channel or marker, and
    ``include_channels`` cannot ask for two channels of one marker (one
    channel is kept per marker).

    Returns:
        One message per conflict; empty if there are none.
    """
    include = list(dict.fromkeys(include_channels))
    exclude = set(exclude_channels)
    use = list(dict.fromkeys(use_markers))
    ignore = set(ignore_markers)
    problems = []

    by_marker: dict[str, list[str]] = {}
    for ch in include:
        by_marker.setdefault(channel_marker(ch), []).append(ch)
    for marker, chans in by_marker.items():
        if len(chans) > 1:
            problems.append(
                f"include_channels lists several channels of marker {marker} "
                f"({', '.join(chans)}). Only one channel per marker is used: keep "
                f"one, or give the rounds different marker names in a manifest "
                f"CSV (e.g. {marker} and {marker}_1)."
            )
    for ch in include:
        if ch in exclude:
            problems.append(f"{ch} is in both include_channels and exclude_channels.")
        marker = channel_marker(ch)
        if marker in ignore:
            problems.append(
                f"include_channels lists {ch}, but marker {marker} is in "
                f"ignore_markers."
            )
        elif use and marker not in use:
            problems.append(
                f"include_channels lists {ch}, but marker {marker} is not in "
                f"use_markers."
            )
    for marker in use:
        if marker in ignore:
            problems.append(
                f"Marker {marker} is in both use_markers and ignore_markers."
            )
    return problems


def check_selection_rules(
    include_channels: Iterable[str] = (),
    exclude_channels: Iterable[str] = (),
    use_markers: Iterable[str] = (),
    ignore_markers: Iterable[str] = (),
) -> None:
    """Raise if the selection settings contradict each other.

    Raises:
        ValueError: Listing every conflict found by
            :func:`selection_rule_conflicts`.
    """
    problems = selection_rule_conflicts(
        include_channels, exclude_channels, use_markers, ignore_markers
    )
    if problems:
        raise ValueError(
            "Contradicting channel selection settings under 'channels:' in your "
            "config YAML file:\n      * " + "\n      * ".join(problems)
        )


def read_manifest(path: str | Path, strict: bool = True) -> list[ChannelRecord]:
    """Read and validate a user-provided manifest CSV.

    Accepts comma, semicolon (written by some spreadsheet programs in many
    locales) or tab delimiters, and a UTF-8 byte-order mark (added by some
    editors).

    Args:
        path: Path to the CSV file.
        strict: Raise on duplicate files or channels. Previews pass ``False``
            to report duplicates instead of failing.

    Returns:
        Validated records sorted by channel name.

    Raises:
        ManifestError: On missing columns, empty cells, bad rounds or
            duplicates. Messages name the offending row.
    """
    path = Path(path)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        text = fh.read()

    header_line = text.splitlines()[0] if text.strip() else ""
    delimiter = max(",;\t", key=header_line.count)
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    columns = [c.strip().lower() for c in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise ManifestError(
            f"{path}: missing required column(s) {missing}; found {columns}. "
            f"Expected a header like: file,marker,round"
        )

    records, problems = [], []
    for row_num, raw in enumerate(reader, start=2):  # row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(row.values()):
            continue  # blank line
        if not row["file"]:
            problems.append(f"row {row_num}: empty 'file'")
            continue
        if not row["marker"]:
            problems.append(f"row {row_num}: empty 'marker' for {row['file']!r}")
            continue
        round_str = row.get("round", "")
        if round_str == "":
            rnd = DEFAULT_ROUND
        elif round_str.isdigit():
            rnd = int(round_str)
        else:
            problems.append(
                f"row {row_num}: round {round_str!r} is not a non-negative integer"
            )
            continue
        use_str = row.get("use", "").lower()
        if use_str == "" or use_str in USE_TRUE:
            use = True
        elif use_str in USE_FALSE:
            use = False
        else:
            problems.append(
                f"row {row_num}: use {row['use']!r} not understood; "
                f"leave it blank or write yes / no"
            )
            continue
        records.append(
            ChannelRecord(file=row["file"], marker=row["marker"], round=rnd, use=use)
        )

    if problems:
        raise ManifestError(f"{path}:\n  - " + "\n  - ".join(problems))
    if not records:
        raise ManifestError(f"{path}: manifest has no entries")

    if strict:
        validate_records(records)
    return sorted(records, key=lambda r: r.channel)


def write_manifest(
    records: Iterable[ChannelRecord],
    path: str | Path,
    unmatched: Iterable[str] = (),
) -> Path:
    """Write records to a CSV that :func:`read_manifest` can read back.

    The ``use`` column is written as ``no`` for records with ``use=False`` and
    left blank otherwise, so the file only ever carries deliberate exclusions,
    never the outcome of the selection rules.

    Args:
        records: Manifest records.
        path: Output CSV path (parent folders are created).
        unmatched: File names without a known marker. They are written after
            the records with empty ``marker`` and ``round`` cells for the user
            to fill in (or delete); :func:`read_manifest` rejects the file
            until they are.

    Returns:
        The path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(OUTPUT_COLUMNS)
        for r in records:
            writer.writerow([r.file, r.marker, r.round, "" if r.use else "no"])
        for name in unmatched:
            writer.writerow([name, "", "", ""])
    return path


def _basename(path: str) -> str:
    """Base name for local (incl. Windows) and remote POSIX paths."""
    return os.path.basename(str(path).replace("\\", "/"))
