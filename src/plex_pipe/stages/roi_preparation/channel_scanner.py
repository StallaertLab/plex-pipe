import os
from collections.abc import Iterable, Sequence

from loguru import logger

from plex_pipe.io.filesystem import list_local_files
from plex_pipe.io.globus import (
    GlobusConfig,
    list_globus_tifs,
)
from plex_pipe.io.channel_manifest import (
    ChannelRecord,
    build_manifest,
    read_manifest,
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
