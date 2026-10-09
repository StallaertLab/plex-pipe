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

from collections.abc import Sequence
from pathlib import Path
from typing import cast

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
from plex_pipe.stages.roi_preparation.cutter import CoreCutter

# ----------------------------------------------------------------------------
# ROI preparation
# ----------------------------------------------------------------------------


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

    do_cleanup = cleanup or bool(config.roi_cutting.transfer_cleanup_enabled)
    transferred = image_path.resolve().is_relative_to(Path(config.temp_dir).resolve())
    if do_cleanup and transferred:
        image_path.unlink()
        logger.info(f"Deleted transferred image {image_path}")


def assemble_roi(config: AnalysisConfig, roi_name: str, channels: Sequence[str]) -> str:
    """Assembles one ROI's channel TIFFs into a SpatialData Zarr store.

    Every channel in ``channels`` must have been cut for this ROI. The TIFFs
    are deleted afterwards if ``roi_cutting.roi_cleanup_enabled`` is true.

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.
        roi_name: Name of the ROI (``roi_name`` in the ROI table).
        channels: Channels to assemble (the selected channels).

    Returns:
        Path to the Zarr store.
    """
    storage = config.sdata_storage
    if None in (storage.chunk_size, storage.max_pyramid_level, storage.downscale):
        raise ValueError(
            "sdata_storage: chunk_size, max_pyramid_level and downscale must be "
            "set (not null) in the config YAML file."
        )
    assembler = CoreAssembler(
        temp_dir=str(config.roi_dir_tif_path),
        output_dir=str(config.roi_dir_output_path),
        max_pyramid_levels=cast(int, storage.max_pyramid_level),
        chunk_size=cast(tuple[int, int, int], tuple(storage.chunk_size or ())),
        downscale=cast(int, storage.downscale),
        allowed_channels=list(channels),
        cleanup=bool(config.roi_cutting.roi_cleanup_enabled),
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
