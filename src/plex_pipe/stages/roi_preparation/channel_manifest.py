"""Channel manifest: the complete inventory of input image files.

A manifest lists **every** input file together with the marker it contains and
the imaging round it was acquired in. It is either generated from file names
with a naming preset (e.g. ``celldive``) or written by the user as a CSV file.

The manifest is a pure inventory: it describes *what exists*. Which channels are
actually used is decided downstream by the selection rules in
:mod:`plex_pipe.stages.roi_preparation.channel_scanner`.

CSV format (header required; comma, semicolon or tab separated)::

    file,marker,round
    BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif,DAPI,1
    BLCA-1_1.0.4_R000_Cy3_pH2AX-AF555_FINAL_AFR_F.ome.tif,pH2AX,1

* ``file``: file name relative to ``general.image_dir``.
* ``marker``: marker name used throughout the pipeline.
* ``round``: optional non-negative integer; a blank cell or a missing column
  means round 1.

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
OUTPUT_COLUMNS = ("file", "marker", "round")


class ManifestError(ValueError):
    """Raised when a channel manifest is malformed or ambiguous."""


@dataclass(frozen=True)
class ChannelRecord:
    """One input file: which marker it holds and in which round."""

    file: str
    marker: str
    round: int = DEFAULT_ROUND

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


###################################################################
# Building, validating, reading and writing manifests
###################################################################


def build_manifest(
    files: Iterable[str], preset: str
) -> tuple[list[ChannelRecord], list[str]]:
    """Generate a manifest from file paths using a naming preset.

    Args:
        files: File paths (local or remote); only the base name is parsed and
            stored.
        preset: Name of a preset in :data:`NAMING_PRESETS`.

    Returns:
        ``(records, unmatched)``: records sorted by channel name, and the base
        names of files the preset did not recognise.

    Raises:
        ManifestError: If the preset is unknown or two files resolve to the
            same channel.
    """
    try:
        parse = NAMING_PRESETS[preset]
    except KeyError:
        raise ManifestError(
            f"Unknown naming preset {preset!r}. "
            f"Available: {sorted(NAMING_PRESETS)}"
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

    validate_records(records)
    return sorted(records, key=lambda r: r.channel), sorted(unmatched)


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
        raise ManifestError("Ambiguous channel manifest:\n  - " + "\n  - ".join(problems))


def read_manifest(path: str | Path) -> list[ChannelRecord]:
    """Read and validate a user-provided manifest CSV.

    Accepts comma, semicolon (Excel in many European locales) or tab
    delimiters, and a UTF-8 byte-order mark (Excel "CSV UTF-8").

    Args:
        path: Path to the CSV file.

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
        row = {
            (k or "").strip().lower(): (v or "").strip() for k, v in raw.items()
        }
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
        records.append(ChannelRecord(file=row["file"], marker=row["marker"], round=rnd))

    if problems:
        raise ManifestError(f"{path}:\n  - " + "\n  - ".join(problems))
    if not records:
        raise ManifestError(f"{path}: manifest has no entries")

    validate_records(records)
    return sorted(records, key=lambda r: r.channel)


def write_manifest(records: Iterable[ChannelRecord], path: str | Path) -> Path:
    """Write records to a CSV that :func:`read_manifest` can read back.

    Args:
        records: Manifest records.
        path: Output CSV path (parent folders are created).

    Returns:
        The path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(OUTPUT_COLUMNS)
        for r in records:
            writer.writerow([r.file, r.marker, r.round])
    return path


def _basename(path: str) -> str:
    """Base name for local (incl. Windows) and remote POSIX paths."""
    return os.path.basename(str(path).replace("\\", "/"))
