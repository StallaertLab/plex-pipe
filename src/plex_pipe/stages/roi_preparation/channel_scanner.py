import os
from collections.abc import Iterable, Sequence

from loguru import logger

from plex_pipe.io.filesystem import list_local_files
from plex_pipe.io.globus import (
    GlobusConfig,
    list_globus_tifs,
)
from plex_pipe.stages.roi_preparation.channel_manifest import (
    ChannelRecord,
    build_manifest,
)

#: Marker treated as the nuclear reference: one round is kept (the earliest).
REFERENCE_MARKER = "DAPI"


def select_channels(
    records: Iterable[ChannelRecord],
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
) -> dict[str, ChannelRecord]:
    """Apply the channel selection rules to a manifest.

    By default the latest round is kept for each marker, except for DAPI, where
    the earliest available round is kept. ``include_channels`` and
    ``exclude_channels`` (channel names such as ``002_CD3``) override this per
    marker; ``use_markers`` and ``ignore_markers`` then filter whole markers.
    See ``docs/configuration/channel-selection.md``.

    Args:
        records: The complete manifest (every input file).
        include_channels: Channel names to keep, bypassing round selection.
        exclude_channels: Channel names to drop before round selection.
        use_markers: If given, keep only these markers.
        ignore_markers: Markers to drop.

    Returns:
        Dictionary mapping marker name to the selected record.

    Raises:
        ValueError: If the manifest is empty.
    """
    include_channels = include_channels or []
    exclude_channels = exclude_channels or []
    use_markers = use_markers or []
    ignore_markers = ignore_markers or []

    records = sorted(records, key=lambda r: r.channel)
    if not records:
        raise ValueError("Channel manifest is empty: no input files to select from.")

    logger.info(f"Discovered {len(records)} channels:")
    for r in records:
        logger.info(f"{r.channel} <- {r.file}")

    grouped: dict[str, list[ChannelRecord]] = {}
    for r in records:
        grouped.setdefault(r.marker, []).append(r)

    result: dict[str, ChannelRecord] = {}

    for marker, items in grouped.items():
        items.sort(key=lambda r: r.round)

        included = [r for r in items if r.channel in include_channels]
        if included:
            for r in included:
                result[marker] = r
            continue

        items = [r for r in items if r.channel not in exclude_channels]
        if not items:
            continue

        if marker.upper() == REFERENCE_MARKER:
            # earliest round (001 for Cell DIVE); keyed as "DAPI"
            result[REFERENCE_MARKER] = items[0]
        else:
            result[marker] = items[-1]

    # Apply filters on markers
    if use_markers:
        for m in use_markers:
            if m not in result:
                logger.warning(f"Requested use_marker '{m}' not found.")

        result = {m: r for m, r in result.items() if m in use_markers}
        logger.info(f"Restricting to use_markers = {use_markers}")
        logger.info(f"Final filtered channels: {list(result.keys())}")

    if ignore_markers:
        for m in ignore_markers:
            if m not in result:
                logger.warning(f"Requested ignore_marker '{m}' not found.")

        result = {m: r for m, r in result.items() if m not in ignore_markers}
        logger.info(f"Ignoring markers = {ignore_markers}")
        logger.info(f"Final filtered channels: {list(result.keys())}")

    # Final report
    selected_files = {r.file for r in result.values()}
    unused = [r for r in records if r.file not in selected_files]

    logger.info(f"Final selected channels {len(result)}:")
    for m in sorted(result, key=str.casefold):
        r = result[m]
        logger.info(f"  Channel: {m} ({r.channel}) <- {r.file}")

    logger.info(f"Files not used in final channel selection {len(unused)}:")
    for r in unused:
        logger.info(f"  Unused: Channel {r.channel} <- {r.file}")

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
    path_by_name = {os.path.basename(str(f).replace("\\", "/")): f for f in files}
    return {m: path_by_name[r.file] for m, r in selected.items()}


def discover_channels(
    image_dir_or_path: str,
    include_channels: list[str] | None = None,
    exclude_channels: list[str] | None = None,
    use_markers: list[str] | None = None,
    ignore_markers: list[str] | None = None,
    gc: GlobusConfig | None = None,
) -> dict[str, str]:
    """Creates a channel map from local or Globus storage.

    This is a convenience wrapper: it obtains a list of candidate OME-TIFF files
    (locally from `image_dir_or_path`, or remotely via Globus when `gc` is provided),
    then delegates marker/round selection to :func:`scan_channels_from_list`.

    Args:
        image_dir_or_path: Local directory path or Globus path to scan.
        include_channels: Specific channel names to include.
        exclude_channels: Specific channel names to exclude.
        use_markers: List of marker names to keep.
        ignore_markers: List of marker names to discard.
        gc: Globus configuration. If provided, scans via Globus API.

    Returns:
        Dictionary mapping marker names to file paths.
    """
    if gc is not None:
        files = list_globus_tifs(gc, image_dir_or_path)
    else:
        files = list_local_files(image_dir_or_path)

    return scan_channels_from_list(
        files, include_channels, exclude_channels, use_markers, ignore_markers
    )
