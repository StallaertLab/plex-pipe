"""Config layer: turns the analysis config into units of work.

The classes in ``plex_pipe.stages`` take explicit arguments and know nothing
about the config file. The functions here read the config, build those
classes and run one unit of work (one channel image or one ROI).

They are shared by everything that runs PlexPipe from a config:

* the scripts in ``scripts/`` loop over all channels / ROIs in one process,
* ``plexpipe`` (``plex_pipe.cli``) runs one unit per call, so a workflow
  manager such as Nextflow can run many in parallel.

Notebooks can call these functions too, or use the classes directly.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
import spatialdata as sd
from loguru import logger

from plex_pipe.config.config_schema import AnalysisConfig
from plex_pipe.ops.registry import build_processor
from plex_pipe.stages.quantification.controller import QuantificationController
from plex_pipe.stages.resource_building.controller import (
    ResourceBuildingController,
)
from plex_pipe.stages.roi_preparation.assembler import CoreAssembler
from plex_pipe.stages.roi_preparation.controller import (
    RoiPreparationController,
)
from plex_pipe.stages.roi_preparation.cutter import CoreCutter
from plex_pipe.stages.roi_preparation.file_strategy import (
    FileAvailabilityStrategy,
    GlobusFileStrategy,
    LocalFileStrategy,
)

if TYPE_CHECKING:
    from plex_pipe.io.globus import GlobusConfig

# Files written by setup() and read by the per-unit commands
IMAGES_FILE = "images.csv"
ROIS_FILE = "rois.csv"
IMAGES_COLUMNS = ("channel", "path", "task_id")
ROIS_COLUMNS = ("roi_name", "path")


def _storage_params(
    config: AnalysisConfig,
) -> tuple[tuple[int, int, int], int, int]:
    """Returns (chunk_size, max_pyramid_level, downscale) from sdata_storage.

    Raises:
        ValueError: If any of them is null in the config.
    """
    storage = config.sdata_storage
    if None in (storage.chunk_size, storage.max_pyramid_level, storage.downscale):
        raise ValueError(
            "sdata_storage: chunk_size, max_pyramid_level and downscale must be "
            "set (not null) in the config YAML file."
        )
    return (
        cast(tuple[int, int, int], tuple(storage.chunk_size or ())),
        cast(int, storage.max_pyramid_level),
        cast(int, storage.downscale),
    )


def cleanup_setting(name: str, flag: bool, config_value: bool | None) -> bool:
    """Combines a cleanup flag of the run with the (older) config key, and logs it.

    Cleanup only changes how much intermediate data stays on disk, not the
    results, so it is a setting of the run: a command-line flag. The config
    keys still work so existing configs keep running.

    Args:
        name: Name of the setting, for the log.
        flag: Value from the command line (or the caller).
        config_value: Value of the matching ``roi_cutting`` key in the config.

    Returns:
        True if cleanup is on.
    """
    if flag:
        logger.info(f"Run setting {name}: on (command line)")
        return True
    if config_value:
        logger.info(f"Run setting {name}: on (config)")
        return True
    logger.info(f"Run setting {name}: off")
    return False


# ----------------------------------------------------------------------------
# Setup for per-unit runs
# ----------------------------------------------------------------------------


def setup(
    config: AnalysisConfig,
    out_dir: str | Path,
    gc: GlobusConfig | None = None,
    file_checksum: bool = False,
) -> tuple[Path, Path]:
    """Prepares a per-unit run: one row per channel and one row per ROI.

    Finds the selected channels (``channels:`` section of the config). With
    ``gc``, starts one Globus transfer per channel into ``temp_dir``; files
    already there are not transferred again unless ``file_checksum`` is true.
    Then writes:

    * ``images.csv`` -- ``channel,path,task_id``: the local path of each
      channel image, and the Globus task to wait for (empty if none),
    * ``rois.csv`` -- ``roi_name,path``: the Zarr store each ROI will get.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        out_dir: Folder for the two CSV files.
        gc: Globus configuration, to fetch the images from a remote collection.
        file_checksum: Transfer files that are already present too (Globus
            then compares checksums).

    Returns:
        Paths of ``images.csv`` and ``rois.csv``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    if gc is not None:
        # cleanup is done after cutting each image (cut_image)
        strategy = GlobusFileStrategy(config=config, gc=gc, cleanup_enabled=False)
        local_paths = {
            ch: gc.destination.globus_to_local(local)
            for ch, (_remote, local) in strategy.transfer_map.items()
        }

        # skip files that are already here, unless a checksum is requested
        if not file_checksum:
            for ch, path in local_paths.items():
                if Path(path).exists():
                    logger.info(f"{ch}: {path} already present; not transferred.")
                    strategy.transfer_map.pop(ch)

        strategy.submit_all_transfers(batch_size=1)
        # batch_size=1: one task per channel, in transfer_map order
        task_ids = dict(zip(strategy.transfer_map, strategy.pending_tasks, strict=True))
        for ch, path in local_paths.items():
            rows.append(
                {"channel": ch, "path": str(path), "task_id": task_ids.get(ch, "")}
            )
    else:
        local = LocalFileStrategy(config=config)
        for ch, image_path in local.channel_map.items():
            rows.append({"channel": ch, "path": str(image_path), "task_id": ""})

    images_file = out_dir / IMAGES_FILE
    with open(images_file, "w", newline="") as f:
        # "\n" line endings: the files are read by shell tools and Nextflow
        writer = csv.DictWriter(f, fieldnames=IMAGES_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {len(rows)} channels to {images_file}")

    df = pd.read_pickle(config.roi_info_file_path)
    rois_file = out_dir / ROIS_FILE
    with open(rois_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ROIS_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for roi in df["roi_name"]:
            path = config.roi_dir_output_path / f"{roi}.zarr"
            writer.writerow({"roi_name": roi, "path": str(path)})
    logger.info(f"Wrote {len(df)} ROIs to {rois_file}")

    return images_file, rois_file


def read_images_file(path: str | Path) -> list[dict[str, str]]:
    """Reads the image list written by :func:`setup`.

    Args:
        path: Path to ``images.csv``.

    Returns:
        One dict per channel with ``channel``, ``path`` and ``task_id``.
    """
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------------------
# ROI preparation
# ----------------------------------------------------------------------------


def prepare_rois(
    config: AnalysisConfig,
    file_strategy: FileAvailabilityStrategy,
    roi_cleanup: bool = False,
) -> RoiPreparationController:
    """Builds the controller that cuts and assembles all ROIs in one process.

    Uses the ROI table at ``roi_info_file_path`` and the ``roi_cutting`` and
    ``sdata_storage`` settings. Call ``.run()`` on the result.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        file_strategy: Where the images come from (local or Globus). Transfer
            cleanup is set on the strategy (``cleanup_enabled``).
        roi_cleanup: Delete the per-ROI TIFFs once each ROI is assembled
            (also on if ``roi_cutting.roi_cleanup_enabled`` is true).

    Returns:
        The controller, ready to run.
    """
    chunk_size, max_pyramid_level, downscale = _storage_params(config)
    return RoiPreparationController(
        metadata_df=pd.read_pickle(config.roi_info_file_path),
        file_strategy=file_strategy,
        temp_dir=str(config.roi_dir_tif_path),
        output_dir=str(config.roi_dir_output_path),
        margin=config.roi_cutting.margin or 0,
        mask_value=config.roi_cutting.mask_value or 0,
        max_pyramid_levels=max_pyramid_level,
        chunk_size=chunk_size,
        downscale=downscale,
        temp_roi_delete=cleanup_setting(
            "roi_cleanup", roi_cleanup, config.roi_cutting.roi_cleanup_enabled
        ),
    )


def cut_image(
    config: AnalysisConfig,
    channel: str,
    image_path: str | Path,
    cleanup: bool = False,
) -> None:
    """Cuts every ROI of the analysis from one channel image.

    Uses ``roi_cutting.margin`` / ``mask_value``, the ROI table at
    ``roi_info_file_path`` and writes the per-ROI TIFFs to ``roi_dir_tif``.

    Afterwards the image is deleted if cleanup is on (``cleanup=True`` or
    ``roi_cutting.transfer_cleanup_enabled``) and the image is a transferred
    copy inside ``temp_dir``. Original images are never deleted.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        channel: Channel name.
        image_path: Path to the channel image.
        cleanup: Delete the transferred image once cut, even if the config
            does not ask for it.

    Raises:
        FileNotFoundError: If the image does not exist.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image for channel {channel}: {image_path}")

    cutter = CoreCutter(
        margin=config.roi_cutting.margin or 0,
        mask_value=config.roi_cutting.mask_value or 0,
    )
    df = pd.read_pickle(config.roi_info_file_path)
    cutter.cut_image(image_path, channel, df, config.roi_dir_tif_path)
    logger.info(f"Cut {len(df)} ROIs from channel {channel}.")

    do_cleanup = cleanup_setting(
        "cleanup", cleanup, config.roi_cutting.transfer_cleanup_enabled
    )
    transferred = image_path.resolve().is_relative_to(Path(config.temp_dir).resolve())
    if do_cleanup and transferred:
        image_path.unlink()
        logger.info(f"Deleted transferred image {image_path}")


def assemble_roi(
    config: AnalysisConfig,
    roi_name: str,
    channels: Sequence[str],
    roi_cleanup: bool = False,
) -> str:
    """Assembles one ROI's channel TIFFs into a SpatialData Zarr store.

    Every channel in ``channels`` must have been cut for this ROI. The TIFFs
    are deleted afterwards if ``roi_cleanup`` (or the older config key
    ``roi_cutting.roi_cleanup_enabled``) is true.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        roi_name: Name of the ROI (``roi_name`` in the ROI table).
        channels: Channels to assemble (the selected channels).
        roi_cleanup: Delete this ROI's TIFFs once it is assembled.

    Returns:
        Path to the Zarr store.
    """
    chunk_size, max_pyramid_level, downscale = _storage_params(config)
    assembler = CoreAssembler(
        temp_dir=str(config.roi_dir_tif_path),
        output_dir=str(config.roi_dir_output_path),
        max_pyramid_levels=max_pyramid_level,
        chunk_size=chunk_size,
        downscale=downscale,
        allowed_channels=list(channels),
        cleanup=cleanup_setting(
            "roi_cleanup", roi_cleanup, config.roi_cutting.roi_cleanup_enabled
        ),
    )
    return assembler.assemble_core(roi_name)


# ----------------------------------------------------------------------------
# Segmentation (resource building)
# ----------------------------------------------------------------------------


def build_resource_controllers(
    config: AnalysisConfig, overwrite: bool = False
) -> list[ResourceBuildingController]:
    """Builds one controller per step in ``additional_elements``.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        overwrite: Whether existing elements may be overwritten.

    Returns:
        The controllers, in the order of the config.
    """
    storage = config.sdata_storage
    if storage.max_pyramid_level is None or storage.downscale is None:
        raise ValueError(
            "sdata_storage: max_pyramid_level and downscale must be set "
            "(not null) in the config YAML file."
        )
    controllers = []
    for step in config.additional_elements or []:
        params = dict(getattr(step, "parameters", None) or {})
        builder = build_processor(step.category, step.type, **params)
        controllers.append(
            ResourceBuildingController(
                builder=builder,
                input_names=step.input,
                output_names=step.output,
                keep=step.keep,
                overwrite=overwrite,
                pyramid_levels=storage.max_pyramid_level,
                downscale=storage.downscale,
                chunk_size=storage.chunk_size,
            )
        )
        logger.info(
            f"Image processor of type '{step.type}' for image '{step.input}' "
            "has been created."
        )
    if not controllers:
        logger.info("No resource builders specified.")
    return controllers


def segment_roi(
    config: AnalysisConfig,
    sdata_path: str | Path,
    controllers: Sequence[ResourceBuildingController],
) -> None:
    """Runs the ``additional_elements`` steps on one ROI.

    Checks first that every step's inputs exist in the ROI (or are made by an
    earlier step).

    Args:
        config: The config the controllers were built from.
        sdata_path: Path to the ROI's SpatialData Zarr store.
        controllers: Controllers from :func:`build_resource_controllers`.
    """
    sdata = sd.read_zarr(sdata_path)
    config.validate_pipeline(sdata)
    for controller in controllers:
        sdata = controller.run(sdata)


# ----------------------------------------------------------------------------
# Quantification
# ----------------------------------------------------------------------------


def build_quant_controllers(
    config: AnalysisConfig, overwrite: bool = False
) -> list[QuantificationController]:
    """Builds one controller per table in the ``quant`` section.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        overwrite: Whether existing tables may be overwritten.

    Returns:
        The controllers, in the order of the config.
    """
    controllers = []
    for quant in config.quant:
        logger.info(
            f"Setting up quantification controller for '{quant.name}' table "
            f"with masks {quant.masks} and connection to "
            f"'{quant.layer_connection}' mask"
        )
        controllers.append(
            QuantificationController(
                table_name=quant.name,
                mask_keys=quant.masks,
                mask_to_annotate=quant.layer_connection,
                markers_to_quantify=quant.markers_to_quantify,
                overwrite=overwrite,
                add_qc_masks=quant.qc_to_table,
                qc_prefix=config.qc.prefix,
            )
        )
    return controllers


def quantify_roi(
    sdata_path: str | Path,
    controllers: Sequence[QuantificationController],
) -> None:
    """Runs every quantification table on one ROI.

    Reusing the same controllers for several ROIs checks that all ROIs have
    the same channels (see :class:`QuantificationController`).

    Args:
        sdata_path: Path to the ROI's SpatialData Zarr store.
        controllers: Controllers from :func:`build_quant_controllers`.
    """
    sdata = sd.read_zarr(sdata_path)
    for controller in controllers:
        controller.run(sdata)
