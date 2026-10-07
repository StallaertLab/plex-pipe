from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from plex_pipe.io.filesystem import list_local_files
from plex_pipe.io.globus import (
    GlobusConfig,
    list_globus_tifs,
)
from plex_pipe.io.channel_manifest import (
    ChannelRecord,
    build_manifest,
    duplicate_channels,
    read_manifest,
    write_manifest,
)

if TYPE_CHECKING:
    import pandas as pd

    from plex_pipe.config.config_schema import AnalysisConfig

#: Marker treated as the nuclear reference: one round is kept (the earliest).
REFERENCE_MARKER = "DAPI"


def explain_selection(
    records: Iterable[ChannelRecord],
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
) -> tuple[dict[str, ChannelRecord], dict[str, str]]:
    """Apply the channel selection rules and explain every decision.

    Order of operations:

    1. Files with ``use=False`` in the manifest are removed first; nothing can
       bring them back (not even ``include_channels``).
    2. Per marker: ``include_channels`` (channel names such as ``002_CD3``)
       pick the channel directly; otherwise ``exclude_channels`` are dropped
       and the latest round is kept, except for DAPI, where the earliest
       round is kept. One channel is kept per marker.
    3. ``use_markers`` then ``ignore_markers`` filter whole markers.

    See ``docs/configuration/channel-selection.md``.

    Args:
        records: The manifest (every input file).
        include_channels: Channel names to keep, bypassing round selection.
        exclude_channels: Channel names to drop before round selection.
        use_markers: If given, keep only these markers.
        ignore_markers: Markers to drop.

    Returns:
        ``(selected, reasons)``: marker -> selected record, and file -> a short
        reason for every file (selected or not).
    """
    include_channels = include_channels or []
    exclude_channels = exclude_channels or []
    use_markers = use_markers or []
    ignore_markers = ignore_markers or []

    reasons: dict[str, str] = {}
    candidates: list[ChannelRecord] = []
    for r in sorted(records, key=lambda r: r.channel):
        if r.use:
            candidates.append(r)
            continue
        reasons[r.file] = "excluded in manifest (use=no)"
        if r.channel in include_channels:
            logger.warning(
                f"include_channels lists {r.channel}, but the manifest excludes "
                f"{r.file} (use=no); the manifest wins."
            )

    grouped: dict[str, list[ChannelRecord]] = {}
    for r in candidates:
        grouped.setdefault(r.marker, []).append(r)

    result: dict[str, ChannelRecord] = {}

    for marker, items in grouped.items():
        items.sort(key=lambda r: r.round)

        included = [r for r in items if r.channel in include_channels]
        if included:
            kept = included[-1]
            result[marker] = kept
            reasons[kept.file] = "selected: include_channels"
            for r in items:
                if r is kept:
                    continue
                reasons[r.file] = (
                    f"include_channels: one channel per marker, kept {kept.channel}"
                    if r in included
                    else f"include_channels selects {kept.channel}"
                )
            continue

        for r in items:
            if r.channel in exclude_channels:
                reasons[r.file] = "exclude_channels"
        items = [r for r in items if r.channel not in exclude_channels]
        if not items:
            continue

        if marker.upper() == REFERENCE_MARKER:
            # earliest round (001 for Cell DIVE); keyed as "DAPI"
            kept = items[0]
            result[REFERENCE_MARKER] = kept
            reasons[kept.file] = (
                "selected: earliest DAPI round" if len(items) > 1 else "selected"
            )
            for r in items[1:]:
                reasons[r.file] = f"DAPI: earliest round {kept.channel} kept"
        else:
            kept = items[-1]
            result[marker] = kept
            reasons[kept.file] = (
                "selected: latest round" if len(items) > 1 else "selected"
            )
            for r in items[:-1]:
                reasons[r.file] = f"superseded by {kept.channel}"

    # Apply filters on markers
    if use_markers:
        for m in use_markers:
            if m not in result:
                logger.warning(f"Requested use_marker '{m}' not found.")
        for m, r in result.items():
            if m not in use_markers:
                reasons[r.file] = "not in use_markers"
        result = {m: r for m, r in result.items() if m in use_markers}

    if ignore_markers:
        for m in ignore_markers:
            if m not in result:
                logger.warning(f"Requested ignore_marker '{m}' not found.")
        for m, r in result.items():
            if m in ignore_markers:
                reasons[r.file] = "ignore_markers"
        result = {m: r for m, r in result.items() if m not in ignore_markers}

    return result, reasons


def select_channels(
    records: Iterable[ChannelRecord],
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
) -> dict[str, ChannelRecord]:
    """Apply the channel selection rules to a manifest and log the outcome.

    See :func:`explain_selection` for the rules and their order.

    Args:
        records: The manifest (every input file).
        include_channels: Channel names to keep, bypassing round selection.
        exclude_channels: Channel names to drop before round selection.
        use_markers: If given, keep only these markers.
        ignore_markers: Markers to drop.

    Returns:
        Dictionary mapping marker name to the selected record.

    Raises:
        ValueError: If the manifest is empty.
    """
    records = sorted(records, key=lambda r: r.channel)
    if not records:
        raise ValueError("Channel manifest is empty: no input files to select from.")

    logger.info(f"Discovered {len(records)} channels:")
    for r in records:
        flag = "" if r.use else " (use=no)"
        logger.info(f"{r.channel} <- {r.file}{flag}")

    n_excluded = sum(not r.use for r in records)
    if n_excluded:
        logger.info(
            f"Manifest column 'use': {n_excluded} file(s) excluded by the manifest; "
            f"roi_cutting rules applied on top."
        )

    result, reasons = explain_selection(
        records, include_channels, exclude_channels, use_markers, ignore_markers
    )

    if use_markers:
        logger.info(f"Restricting to use_markers = {use_markers}")
    if ignore_markers:
        logger.info(f"Ignoring markers = {ignore_markers}")

    # Final report
    selected_files = {r.file for r in result.values()}
    unused = [r for r in records if r.file not in selected_files]

    logger.info(f"Final selected channels {len(result)}:")
    for m in sorted(result, key=str.casefold):
        r = result[m]
        logger.info(f"  Channel: {m} ({r.channel}) <- {r.file}")

    logger.info(f"Files not used in final channel selection {len(unused)}:")
    for r in unused:
        logger.info(f"  Unused: Channel {r.channel} <- {r.file} ({reasons[r.file]})")

    return result


def log_unmatched(unmatched: Sequence[str], preset: str) -> None:
    """Log files that a naming preset did not recognise."""
    if not unmatched:
        return
    logger.info(
        f"Files not recognised by naming preset '{preset}' {len(unmatched)}:"
    )
    for name in unmatched:
        logger.info(f"  Unrecognised: {name}")


def scan_channels_from_list(
    files: Sequence[str],
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
    preset: str = "celldive",
) -> dict[str, str]:
    """Build a channel map from a list of file paths.

    Builds the manifest from file names with a naming preset, then applies
    :func:`select_channels`.

    Args:
        files: List of file paths to process.
        include_channels: Specific channel names to include, bypassing selection.
        exclude_channels: Specific channel names to exclude.
        use_markers: List of marker names to keep.
        ignore_markers: List of marker names to discard.
        preset: Naming preset used to parse file names.

    Returns:
        Dictionary mapping marker names to file paths (as given in ``files``).

    Raises:
        ValueError: If no file is recognised by the preset.
    """
    records, unmatched = build_manifest(files, preset)
    log_unmatched(unmatched, preset)

    if not records:
        msg = f"No files recognised by naming preset '{preset}' in {list(files)}"
        raise ValueError(msg)

    selected = select_channels(
        records, include_channels, exclude_channels, use_markers, ignore_markers
    )

    # records store base names; map back to the paths that were listed
    path_by_name = _paths_by_name(files)
    return {m: path_by_name[r.file] for m, r in selected.items()}


def scan_channels_from_manifest(
    manifest_path: str,
    files: Sequence[str],
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
) -> dict[str, str]:
    """Build a channel map from a user-provided manifest CSV.

    The manifest says which marker and round each file holds; ``files`` (the
    listing of ``image_dir``) is used to check that every listed file exists
    and to return full paths.

    Args:
        manifest_path: Path to the manifest CSV.
        files: Paths of the files present in ``image_dir``.
        include_channels: Specific channel names to include, bypassing selection.
        exclude_channels: Specific channel names to exclude.
        use_markers: List of marker names to keep.
        ignore_markers: List of marker names to discard.

    Returns:
        Dictionary mapping marker names to file paths (as given in ``files``).

    Raises:
        ManifestError: If the manifest is malformed.
        ValueError: If the manifest lists files that are not in ``image_dir``.
    """
    records = read_manifest(manifest_path)
    path_by_name = _paths_by_name(files)

    missing = [r.file for r in records if r.file not in path_by_name]
    if missing:
        raise ValueError(
            f"Channel manifest {manifest_path} lists {len(missing)} file(s) not "
            f"found in image_dir: {missing}. The 'file' column must hold file "
            f"names in image_dir."
        )

    in_manifest = {r.file for r in records}
    unlisted = sorted(n for n in path_by_name if n not in in_manifest)
    if unlisted:
        logger.info(f"Files in image_dir not listed in the manifest {len(unlisted)}:")
        for name in unlisted:
            logger.info(f"  Not in manifest: {name}")

    selected = select_channels(
        records, include_channels, exclude_channels, use_markers, ignore_markers
    )
    return {m: path_by_name[r.file] for m, r in selected.items()}


def _paths_by_name(files: Sequence[str]) -> dict[str, str]:
    """Map base names (local, Windows or remote POSIX paths) to listed paths."""
    return {os.path.basename(str(f).replace("\\", "/")): f for f in files}


def discover_channels(
    image_dir_or_path: str,
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
    gc: GlobusConfig | None = None,
    file_naming: str | None = "celldive",
    channel_manifest: str | None = None,
) -> dict[str, str]:
    """Creates a channel map from local or Globus storage.

    Lists the TIFF files in `image_dir_or_path` (locally, or remotely via Globus
    when `gc` is provided), builds the channel manifest, then applies the
    selection rules. The manifest comes from `channel_manifest` (a CSV) when
    given, otherwise from the file names via the `file_naming` preset.

    Args:
        image_dir_or_path: Local directory path or Globus path to scan.
        include_channels: Specific channel names to include.
        exclude_channels: Specific channel names to exclude.
        use_markers: List of marker names to keep.
        ignore_markers: List of marker names to discard.
        gc: Globus configuration. If provided, scans via Globus API.
        file_naming: Naming preset used when no manifest is given.
        channel_manifest: Path to a manifest CSV; takes precedence over
            `file_naming`.

    Returns:
        Dictionary mapping marker names to file paths.
    """
    if gc is not None:
        files = list_globus_tifs(gc, image_dir_or_path)
    else:
        files = list_local_files(image_dir_or_path)

    rules = (include_channels, exclude_channels, use_markers, ignore_markers)

    if channel_manifest is not None:
        logger.info(
            f"Channel source: manifest {channel_manifest} "
            f"(image_dir: {image_dir_or_path})"
        )
        return scan_channels_from_manifest(channel_manifest, files, *rules)

    preset = file_naming or "celldive"
    logger.info(
        f"Channel source: naming preset '{preset}' (image_dir: {image_dir_or_path})"
    )
    return scan_channels_from_list(files, *rules, preset=preset)


PREVIEW_COLUMNS = ("file", "marker", "round", "use", "channel", "selected", "reason")


def preview_channels(
    config: AnalysisConfig,
    gc: GlobusConfig | None = None,
    preset: str | None = None,
) -> pd.DataFrame:
    """Dry run of channel discovery: what will be cut, and why.

    Lists ``general.image_dir`` (locally, or over Globus when ``gc`` is given),
    builds the manifest exactly as a run would (from ``general.channel_manifest``
    if set, otherwise with the naming preset), applies the ``roi_cutting``
    selection rules, and returns one row per file. Unlike a run it never stops
    at the first problem: unrecognised files, duplicate channels, files missing
    from ``image_dir`` and files not in the manifest are reported as rows.

    To get an editable manifest CSV, call :func:`save_manifest` with the same
    config (it does not need this table).

    Args:
        config: The analysis configuration.
        gc: Globus configuration, if ``image_dir`` is on a Globus endpoint.
        preset: Force this naming preset, ignoring ``general.channel_manifest``
            (e.g. to start a fresh manifest).

    Returns:
        DataFrame with columns ``file, marker, round, use, channel, selected,
        reason``. Selected and candidate rows come first (by channel), then
        rows needing attention.

    Raises:
        ValueError: If ``image_dir`` contains no TIFF files.
        ManifestError: If ``general.channel_manifest`` cannot be parsed.
    """
    import pandas as pd

    general, cutting = config.general, config.roi_cutting
    image_dir = general.image_dir
    files = list_globus_tifs(gc, image_dir) if gc is not None else list_local_files(
        image_dir
    )
    if not files:
        raise ValueError(f"No TIFF files found in image_dir: {image_dir}")
    path_by_name = _paths_by_name(files)

    problem_rows: list[dict] = []

    def blank_row(name: str, reason: str) -> dict:
        return dict(file=name, marker="", round=None, use=True, channel="",
                    selected=False, reason=reason)

    def record_row(r: ChannelRecord, selected: bool, reason: str) -> dict:
        return dict(file=r.file, marker=r.marker, round=r.round, use=r.use,
                    channel=r.channel, selected=selected, reason=reason)

    if preset is None and general.channel_manifest is not None:
        source = f"manifest {general.channel_manifest}"
        records = read_manifest(general.channel_manifest, strict=False)
        in_manifest = {r.file for r in records}
        for r in records:
            if r.file not in path_by_name:
                problem_rows.append(record_row(r, False, "missing from image_dir"))
        records = [r for r in records if r.file in path_by_name]
        for name in sorted(path_by_name):
            if name not in in_manifest:
                problem_rows.append(blank_row(name, "not in manifest"))
    else:
        preset = preset or general.file_naming or "celldive"
        source = f"naming preset '{preset}'"
        records, unmatched = build_manifest(files, preset, strict=False)
        for name in unmatched:
            problem_rows.append(blank_row(name, f"not recognised by {source}"))

    dups = duplicate_channels(records)
    for r in records:
        if r.channel in dups:
            others = [f for f in dups[r.channel] if f != r.file]
            problem_rows.append(
                record_row(r, False, f"duplicate channel {r.channel} (also {others})")
            )
    candidates = [r for r in records if r.channel not in dups]

    selected, reasons = explain_selection(
        candidates,
        cutting.include_channels,
        cutting.exclude_channels,
        cutting.use_markers,
        cutting.ignore_markers,
    )
    selected_files = {r.file for r in selected.values()}
    rows = [
        record_row(r, r.file in selected_files, reasons[r.file])
        for r in sorted(candidates, key=lambda r: r.channel)
    ]

    table = pd.DataFrame(rows + problem_rows, columns=list(PREVIEW_COLUMNS))
    table["round"] = table["round"].astype("Int64")

    logger.info(
        f"Channel preview ({source}, image_dir: {image_dir}): "
        f"{len(selected_files)} of {len(table)} files selected, "
        f"{len(problem_rows)} need attention."
    )
    return table


#: File name used by :func:`save_manifest` when no path is given.
DEFAULT_MANIFEST_NAME = "channels.csv"


def save_manifest(
    config: AnalysisConfig,
    out_path: str | Path | None = None,
    gc: GlobusConfig | None = None,
    preset: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Write an editable manifest CSV for ``general.image_dir``.

    Builds the manifest the same way :func:`preview_channels` does (from
    ``general.channel_manifest`` if set, otherwise with the naming preset) and
    writes only ``file, marker, round, use``. The selection rules are not
    saved: they are re-applied on every run. ``use`` is written as ``no`` only
    for files already excluded in the manifest and left blank otherwise. Rows
    needing attention are kept (blank marker, or duplicate channels) so the
    user can fix them; files missing from ``image_dir`` are dropped with a
    warning.

    Workflow: edit the CSV (e.g. in Excel), then set
    ``general.channel_manifest: <path>`` and remove ``general.file_naming``.

    Args:
        config: The analysis configuration.
        out_path: Where to write the CSV. Defaults to ``channels.csv`` in the
            analysis directory (``general.analysis_dir/general.analysis_name``).
        gc: Globus configuration, if ``image_dir`` is on a Globus endpoint.
        preset: Force this naming preset, ignoring ``general.channel_manifest``
            (e.g. to start a fresh manifest).
        overwrite: Replace ``out_path`` if it exists. Off by default so a
            hand-edited manifest is never lost by accident.

    Returns:
        The path written.

    Raises:
        FileExistsError: If ``out_path`` exists and ``overwrite`` is False.
        ValueError: If ``image_dir`` contains no TIFF files.
    """
    if out_path is None:
        out_path = Path(config.analysis_dir) / DEFAULT_MANIFEST_NAME
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(
            f"{out_path} already exists. Pass overwrite=True to replace it."
        )

    table = preview_channels(config, gc=gc, preset=preset)

    missing = table[table["reason"] == "missing from image_dir"]
    if len(missing):
        logger.warning(
            f"Not saving {len(missing)} file(s) missing from image_dir: "
            f"{missing['file'].tolist()}"
        )
    table = table[table["reason"] != "missing from image_dir"]

    has_marker = table["marker"].astype(str).str.strip() != ""
    records = [
        ChannelRecord(file=row.file, marker=row.marker, round=int(row.round),
                      use=bool(row.use))
        for row in table[has_marker].itertuples()
    ]
    unmatched = table.loc[~has_marker, "file"].tolist()
    write_manifest(records, out_path, unmatched=unmatched)

    n_dup = sum(table["reason"].str.startswith("duplicate channel"))
    logger.info(
        f"Wrote channel manifest {out_path}: {len(records)} files with a marker, "
        f"{len(unmatched)} left blank."
    )
    if unmatched or n_dup:
        logger.warning(
            f"Before using {out_path}: fill in or delete the {len(unmatched)} "
            f"row(s) with an empty marker, and resolve {n_dup} duplicate-channel "
            f"row(s) (rename a marker, e.g. CD45 -> CD45_1, or set use=no)."
        )
    logger.info(
        f"To use it, set general.channel_manifest: {out_path} "
        f"(and remove general.file_naming)."
    )
    return out_path
