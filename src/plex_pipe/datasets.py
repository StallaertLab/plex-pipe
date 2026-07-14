"""Downloadable example data for the plex_pipe quickstart.

The example dataset is hosted on a dedicated GitHub data release
(:data:`EXAMPLE_DATA_TAG`), versioned independently of the plex_pipe package, so
it changes only when a new data release is cut, not on every code release.

The archive is retrieved with ``pooch``, which downloads it once, caches it
locally, and validates it against the SHA256 recorded in this module. Keeping the
checksum in source, rather than alongside the data, is what allows a corrupted
download or a substituted remote file to be detected.

Updating the example data: upload a new archive to a new data release, then
update :data:`EXAMPLE_DATA_TAG` and :data:`EXAMPLE_DATA_SHA256`.
"""

from __future__ import annotations

from pathlib import Path

import pooch
from loguru import logger

#: Tag of the GitHub release that carries the example data.
EXAMPLE_DATA_TAG = "example-data-v1"

#: Name of the archive attached to that release.
EXAMPLE_DATA_ARCHIVE = "plexpipe_example_data.zip"

#: SHA256 of the archive. Update whenever the example data changes.
EXAMPLE_DATA_SHA256 = (
    "2ab09badbe18ec8c39dcb1206f158bba0c2b6667330039b8b11dcae7bb9d0b8c"
)

#: Location the archive is downloaded from.
EXAMPLE_DATA_BASE_URL = (
    "https://github.com/StallaertLab/plex-pipe/releases/download/"
    f"{EXAMPLE_DATA_TAG}/"
)

# Pooch handles the download, the local cache, and the checksum validation.
# ``env`` allows the cache location to be overridden with the PLEX_PIPE_DATA_DIR
# environment variable, for example on HPC systems with a constrained home
# directory.
_REGISTRY = pooch.create(
    path=pooch.os_cache("plex_pipe"),
    base_url=EXAMPLE_DATA_BASE_URL,
    registry={EXAMPLE_DATA_ARCHIVE: f"sha256:{EXAMPLE_DATA_SHA256}"},
    env="PLEX_PIPE_DATA_DIR",
)

_IMAGE_SUFFIXES = (".tif", ".tiff")


def fetch_example() -> Path:
    """Download and unpack the example dataset, returning its image directory.

    The dataset contains DAPI plus three markers (bCat, CD45, NaKATPase) across
    two TMA cores at full resolution: raw intensities, without annotations.

    On the first call the archive is downloaded from the data release, validated
    against :data:`EXAMPLE_DATA_SHA256`, and unzipped into a local cache.
    Subsequent calls reuse the cache and require no network access. The cache is
    disposable: if it is deleted, the next call downloads the archive again.

    Returns:
        Path to the directory holding the example ``.tiff`` images, suitable for
        use as the config's ``general.image_dir``.

    Raises:
        RuntimeError: If the archive unpacks without any images, indicating a
            corrupt archive or a change to its internal layout.
    """
    paths = _REGISTRY.fetch(EXAMPLE_DATA_ARCHIVE, processor=pooch.Unzip())

    images = sorted(
        Path(p) for p in paths if Path(p).suffix.lower() in _IMAGE_SUFFIXES
    )
    if not images:
        raise RuntimeError(
            f"No {' / '.join(_IMAGE_SUFFIXES)} images found in "
            f"{EXAMPLE_DATA_ARCHIVE}. The archive may be corrupt, or its "
            f"internal layout may have changed."
        )

    image_dir = images[0].parent
    logger.info(f"Example data ready: {len(images)} images in {image_dir}")
    return image_dir
