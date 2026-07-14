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

import shutil
import zipfile
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


def _unpack_images_into(archive: Path, dest: Path) -> list[Path]:
    """Extract the image files from ``archive`` into ``dest``.

    The archive's internal folder structure is flattened, so the images land
    directly in ``dest``. Files already present are left untouched, which makes
    repeated calls cheap and safe to re-run.

    Args:
        archive: Path to the downloaded zip archive.
        dest: Directory to write the images into.

    Returns:
        Sorted paths of the images now present in ``dest``.
    """
    unpacked: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if not name or Path(name).suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            target = dest / name
            if not target.exists():
                with zf.open(member) as source, open(target, "wb") as output:
                    shutil.copyfileobj(source, output)
            unpacked.append(target)
    return sorted(unpacked)


def fetch_example(dest: str | Path | None = None) -> Path:
    """Download and unpack the example dataset, returning its image directory.

    The dataset contains DAPI plus three markers (bCat, CD45, NaKATPase) across
    two TMA cores at full resolution: raw intensities, without annotations.

    On the first call the archive is downloaded from the data release and
    validated against :data:`EXAMPLE_DATA_SHA256`. Subsequent calls reuse the
    cached archive and require no network access. The cache is disposable: if it
    is deleted, the next call downloads the archive again.

    Args:
        dest: Directory to unpack the images into. Supplying a path means a
            config whose ``general.image_dir`` already points at that directory
            works unchanged, which keeps the config file the single source of
            truth for where the data lives. When omitted, the images are
            unpacked into the local cache and that location is returned instead.

    Returns:
        Path to the directory holding the example ``.tiff`` images, suitable for
        use as the config's ``general.image_dir``.

    Raises:
        RuntimeError: If the archive contains no images, indicating a corrupt
            archive or a change to its internal layout.
    """
    if dest is None:
        paths = _REGISTRY.fetch(EXAMPLE_DATA_ARCHIVE, processor=pooch.Unzip())
        images = sorted(
            Path(p) for p in paths if Path(p).suffix.lower() in _IMAGE_SUFFIXES
        )
        image_dir = images[0].parent if images else None
    else:
        image_dir = Path(dest)
        image_dir.mkdir(parents=True, exist_ok=True)
        archive = Path(_REGISTRY.fetch(EXAMPLE_DATA_ARCHIVE))
        images = _unpack_images_into(archive, image_dir)

    if not images or image_dir is None:
        raise RuntimeError(
            f"No {' / '.join(_IMAGE_SUFFIXES)} images found in "
            f"{EXAMPLE_DATA_ARCHIVE}. The archive may be corrupt, or its "
            f"internal layout may have changed."
        )

    logger.info(f"Example data ready: {len(images)} images in {image_dir}")
    return image_dir
