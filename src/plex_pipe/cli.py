"""Command-line interface for running PlexPipe one unit at a time.

``plexpipe <command>`` runs one unit of work: one channel image or one ROI.
It is meant for workflow managers such as Nextflow, which start one job per
unit. To run a whole analysis in one process, use the scripts in
``scripts/`` instead; both call the same functions in ``plex_pipe.runners``.

Commands:
    setup         Find the channels, start Globus transfers, write the lists
                  of images and ROIs that the other commands take.
    cut-image     Cut every ROI from one channel image.
    assemble-roi  Assemble one ROI's channel TIFFs into a SpatialData store.
    segment-roi   Run the ``additional_elements`` steps on one ROI.
    quantify-roi  Run the ``quant`` tables on one ROI.

Every command takes ``--exp_config``. All paths in that config must be
absolute, because each job may run in a different working directory.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from plex_pipe.config.config_schema import AnalysisConfig


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def relative_config_paths(config: AnalysisConfig) -> dict[str, str]:
    """Returns the config paths that are relative (name -> path).

    Args:
        config: A config returned by :func:`plex_pipe.load_config`.

    Returns:
        The relative paths, keyed by their name in the config.
    """
    paths: dict[str, Any] = {
        "general.image_dir": config.general.image_dir,
        "general.analysis_dir": config.analysis_dir,
        "general.log_dir": config.log_dir_path,
        "roi_definition.roi_info_file_path": config.roi_info_file_path,
        "roi_cutting.roi_dir_tif": config.roi_dir_tif_path,
        "roi_cutting.roi_dir_output": config.roi_dir_output_path,
        "channels.manifest": config.channels.manifest,
    }
    return {
        name: str(path)
        for name, path in paths.items()
        if path is not None and not Path(path).is_absolute()
    }


def load_job_config(exp_config: str, command: str, unit: str) -> AnalysisConfig:
    """Loads the config, starts logging and records the config snapshot.

    Args:
        exp_config: Path to the config YAML file.
        command: Name of the command (used in the log file name).
        unit: The channel or ROI this job works on (used in the log file name).

    Returns:
        The loaded config.

    Raises:
        ValueError: If any path in the config is relative.
    """
    from plex_pipe.config.config_loaders import (
        load_config,
        save_config_snapshot,
    )

    config = load_config(exp_config)

    relative = relative_config_paths(config)
    if relative:
        lines = "\n".join(f"  - {k}: {v}" for k, v in relative.items())
        raise ValueError(
            f"Config '{exp_config}' has relative paths:\n{lines}\n"
            "plexpipe commands may run in a different folder for every job, "
            "so all paths in the config YAML file must be absolute."
        )

    stamp = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    log_file = config.log_dir_path / f"{command}_{unit}_{stamp}.log"
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    logger.add(log_file, level="DEBUG", enqueue=True)
    logger.info(f"plexpipe {command}: {unit}")

    save_config_snapshot(config)
    return config


def wait_for_globus_task(
    tc: Any, task_id: str, timeout_hours: float, poll_seconds: float
) -> None:
    """Waits until a Globus transfer task has succeeded.

    Args:
        tc: Globus TransferClient.
        task_id: ID of the transfer task.
        timeout_hours: How long to wait before giving up.
        poll_seconds: Seconds between status checks.

    Raises:
        RuntimeError: If the task failed.
        TimeoutError: If the task did not finish in time.
    """
    end = time.monotonic() + timeout_hours * 3600
    while True:
        status = tc.get_task(task_id)["status"]
        if status == "SUCCEEDED":
            logger.info(f"Globus task {task_id} succeeded.")
            return
        if status == "FAILED":
            raise RuntimeError(f"Globus task {task_id} failed.")
        if time.monotonic() >= end:
            raise TimeoutError(
                f"Globus task {task_id} not finished after {timeout_hours} h "
                f"(status {status})."
            )
        logger.debug(f"Globus task {task_id}: {status}; waiting.")
        time.sleep(poll_seconds)


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------


def cmd_setup(args: argparse.Namespace) -> None:
    """Finds channels, starts transfers and writes the image and ROI lists."""
    from plex_pipe.runners import setup

    config = load_job_config(args.exp_config, "setup", "analysis")

    gc = None
    if args.globus_config:
        from plex_pipe.io.globus import GlobusConfig

        gc = GlobusConfig.from_yaml(
            args.globus_config,
            source_key=args.from_collection,
            dest_key=args.to_collection,
        )

    setup(config, args.out_dir, gc=gc, file_checksum=args.file_checksum)


def cmd_cut_image(args: argparse.Namespace) -> None:
    """Cuts every ROI from one channel image."""
    from plex_pipe.runners import cut_image

    config = load_job_config(args.exp_config, "cut-image", args.channel)

    if args.task_id:
        if not args.globus_config:
            raise ValueError("--task_id needs --globus_config.")
        from plex_pipe.io.globus import GlobusConfig, create_globus_tc

        gc = GlobusConfig.from_yaml(
            args.globus_config,
            source_key=args.from_collection,
            dest_key=args.to_collection,
        )
        tc = create_globus_tc(gc.client_id, gc.transfer_tokens)
        wait_for_globus_task(tc, args.task_id, args.wait_hours, args.poll_seconds)

    cut_image(config, args.channel, args.image_path, cleanup=args.cleanup)


def cmd_assemble_roi(args: argparse.Namespace) -> None:
    """Assembles one ROI from its channel TIFFs."""
    from plex_pipe.runners import assemble_roi, read_images_file

    config = load_job_config(args.exp_config, "assemble-roi", args.roi)
    channels = [row["channel"] for row in read_images_file(args.images)]
    assemble_roi(config, args.roi, channels, roi_cleanup=args.roi_cleanup)


def cmd_segment_roi(args: argparse.Namespace) -> None:
    """Runs the additional_elements steps on one ROI."""
    from plex_pipe.runners import build_resource_controllers, segment_roi

    config = load_job_config(args.exp_config, "segment-roi", Path(args.roi_path).stem)
    controllers = build_resource_controllers(config, overwrite=args.overwrite)
    segment_roi(config, args.roi_path, controllers)


def cmd_quantify_roi(args: argparse.Namespace) -> None:
    """Runs the quant tables on one ROI."""
    from plex_pipe.runners import build_quant_controllers, quantify_roi

    config = load_job_config(args.exp_config, "quantify-roi", Path(args.roi_path).stem)
    controllers = build_quant_controllers(config, overwrite=args.overwrite)
    quantify_roi(args.roi_path, controllers)


# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------


def _add_globus_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--globus_config", help="Path to the Globus config YAML.")
    parser.add_argument(
        "--from_collection",
        default="remote_source",
        help="Key of the source collection in the Globus config.",
    )
    parser.add_argument(
        "--to_collection",
        default="local_workstation",
        help="Key of the destination collection (this machine).",
    )


def build_parser() -> argparse.ArgumentParser:
    """Builds the ``plexpipe`` argument parser."""
    from plex_pipe import __version__

    parser = argparse.ArgumentParser(
        prog="plexpipe",
        description="Run PlexPipe one channel image or one ROI at a time.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func: Any, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument(
            "--exp_config", required=True, help="Path to the config YAML file."
        )
        p.set_defaults(func=func)
        return p

    p = add(
        "setup",
        cmd_setup,
        "Find the channels, start Globus transfers and write images.csv "
        "and rois.csv.",
    )
    p.add_argument("--out_dir", default=".", help="Folder for images.csv and rois.csv.")
    _add_globus_args(p)
    p.add_argument(
        "--file_checksum",
        action="store_true",
        help="Transfer files that are already present too (Globus checks "
        "their checksums).",
    )

    p = add("cut-image", cmd_cut_image, "Cut every ROI from one channel image.")
    p.add_argument("--channel", required=True, help="Channel name.")
    p.add_argument("--image_path", required=True, help="Path to the image.")
    _add_globus_args(p)
    p.add_argument(
        "--task_id", help="Globus task to wait for before cutting (from setup)."
    )
    p.add_argument(
        "--wait_hours",
        type=float,
        default=12,
        help="How long to wait for the Globus task (hours).",
    )
    p.add_argument(
        "--poll_seconds",
        type=float,
        default=30,
        help="Seconds between Globus status checks.",
    )
    p.add_argument(
        "--cleanup",
        "-c",
        action="store_true",
        help="Delete the transferred image once cut (Globus runs only).",
    )

    p = add(
        "assemble-roi",
        cmd_assemble_roi,
        "Assemble one ROI's channel TIFFs into a SpatialData store.",
    )
    p.add_argument("--roi", required=True, help="ROI name (roi_name).")
    p.add_argument("--images", required=True, help="images.csv written by setup.")
    p.add_argument(
        "--roi_cleanup",
        action="store_true",
        help="Delete this ROI's TIFFs once it is assembled.",
    )

    for name, func, text in (
        ("segment-roi", cmd_segment_roi, "Run additional_elements on one ROI."),
        ("quantify-roi", cmd_quantify_roi, "Run the quant tables on one ROI."),
    ):
        p = add(name, func, text)
        p.add_argument(
            "--roi_path", required=True, help="Path to the ROI's .zarr store."
        )
        p.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing elements or tables.",
        )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point of the ``plexpipe`` command."""
    args = build_parser().parse_args(argv)
    args.func(args)
