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

:func:`setup_example` builds on :func:`fetch_example`: it also writes a
ready-to-use config and a small ROI table, so the example runs after a plain
``pip install``, without a clone of the repository.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
import pooch
from loguru import logger

#: Tag of the GitHub release that carries the example data.
EXAMPLE_DATA_TAG = "example-data-v1"

#: Name of the archive attached to that release.
EXAMPLE_DATA_ARCHIVE = "plexpipe_example_data.zip"

#: SHA256 of the archive. Update whenever the example data changes.
EXAMPLE_DATA_SHA256 = "2ab09badbe18ec8c39dcb1206f158bba0c2b6667330039b8b11dcae7bb9d0b8c"

#: Location the archive is downloaded from.
EXAMPLE_DATA_BASE_URL = (
    f"https://github.com/plexpipe/plex-pipe/releases/download/{EXAMPLE_DATA_TAG}/"
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


#: Side length, in full-resolution pixels, of the example ROIs.
EXAMPLE_ROI_SIZE = 512

#: Top-left corners (row, column) of the example ROIs, inside the two tissue
#: cores of the example images. Small on purpose: the whole example runs in
#: about a minute. Draw your own ROIs with the napari ``RoiWidget``.
EXAMPLE_ROI_CORNERS = {"ROI_000": (2400, 2400), "ROI_001": (2200, 9948)}

#: Analysis name used in the example config.
EXAMPLE_ANALYSIS_NAME = "example"


def example_roi_table() -> pd.DataFrame:
    """Returns the example ROI table (rectangles, full-resolution pixels).

    Same columns as the table the ROI definition step saves.
    """
    rows = []
    for name, (r0, c0) in EXAMPLE_ROI_CORNERS.items():
        r1, c1 = r0 + EXAMPLE_ROI_SIZE, c0 + EXAMPLE_ROI_SIZE
        rows.append(
            {
                "roi_name": name,
                "row_start": float(r0),
                "row_stop": float(r1),
                "column_start": float(c0),
                "column_stop": float(c1),
                "poly_type": "rectangle",
                "polygon_vertices": np.array(
                    [[r0, c1], [r1, c1], [r1, c0], [r0, c0]], dtype=float
                ),
            }
        )
    return pd.DataFrame(rows)


def _set_general(text: str, key: str, value: str) -> str:
    """Replaces the value of ``general.<key>`` in the config text, keeping comments."""
    pattern = re.compile(rf'^(  {key}: )"[^"]*"(.*)$', flags=re.M)

    def replace(match: re.Match[str]) -> str:
        return f'{match.group(1)}"{value}"{match.group(2)}'

    new, count = pattern.subn(replace, text)
    if count != 1:
        raise RuntimeError(f"Example config template: expected one '{key}:' line.")
    return new


def example_config_text(image_dir: Path, analysis_dir: Path) -> str:
    """Returns the example config, with absolute paths to the given folders.

    The template is ``plex_pipe/example_config.yaml`` (a copy of
    ``examples/example_pipeline_config.yaml``); its comments are kept.
    """
    text = (files("plex_pipe") / "example_config.yaml").read_text(encoding="utf-8")
    text = _set_general(text, "image_dir", Path(image_dir).as_posix())
    text = _set_general(text, "analysis_name", EXAMPLE_ANALYSIS_NAME)
    text = _set_general(text, "analysis_dir", Path(analysis_dir).as_posix())
    return text


def setup_example(dest: str | Path) -> Path:
    """Sets up a ready-to-run example analysis and returns its config path.

    Creates, in ``dest``:

    * ``input/``: the example images (see :func:`fetch_example`),
    * ``config.yaml``: the example config, with absolute paths to ``input/``
      and ``output/``,
    * ``output/example/rois.pkl`` (and ``rois.csv``): two small ROIs
      (:data:`EXAMPLE_ROI_CORNERS`), so the ROI definition step can be skipped.

    Files that already exist are left unchanged, so your edits to the config
    survive a second call.

    Args:
        dest: Folder for the example (created if needed).

    Returns:
        Path to ``config.yaml``, ready for :func:`plex_pipe.load_config`.
    """
    from plex_pipe.config.config_loaders import load_config

    dest = Path(dest).resolve()
    image_dir = fetch_example(dest / "input")

    config_path = dest / "config.yaml"
    if config_path.exists():
        logger.info(f"Keeping the existing config {config_path}")
    else:
        config_path.write_text(
            example_config_text(image_dir, dest / "output"), encoding="utf-8"
        )
        logger.info(f"Example config written: {config_path}")

    config = load_config(config_path)
    rois = config.roi_info_file_path
    if rois.exists():
        logger.info(f"Keeping the existing ROI table {rois}")
    else:
        rois.parent.mkdir(parents=True, exist_ok=True)
        table = example_roi_table()
        table.to_pickle(rois)
        table.to_csv(rois.with_suffix(".csv"), index=False)
        logger.info(f"Example ROIs written: {rois} ({len(table)} ROIs)")

    return config_path
