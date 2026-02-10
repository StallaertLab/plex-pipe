import argparse
import os
import sys
from datetime import datetime

import spatialdata as sd
from loguru import logger

from plex_pipe.object_quantification.controller import QuantificationController
from plex_pipe.utils.config_loaders import load_analysis_settings


def configure_logging(settings):
    """
    Setup logging.
    """

    log_file = (
        settings.log_dir_path
        / f"rois_quantification_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    )

    logger.remove()
    logger.add(sys.stdout, level="DEBUG")
    logger.add(log_file, level="DEBUG", enqueue=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Quantify objects from segmented ROIS using the provided config file."
    )

    parser.add_argument(
        "--exp_config", help="Path to experiment YAML config.", required=True
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Should the masks be overwritten.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    # read config file
    settings = load_analysis_settings(args.exp_config)

    # setup logging
    configure_logging(settings)
    logger.info("Starting quantification script.")

    # setup quantification controllers
    quant_controller_list = []
    qc_prefix = settings.qc.prefix
    for quant in settings.quant:

        table_name = quant.name
        masks_keys = quant.masks
        mask_to_annotate = quant.layer_connection

        logger.info(
            f"Setting up quantification controller for '{table_name}' table with masks {masks_keys} and connection to '{mask_to_annotate}' mask"
        )

        controller = QuantificationController(
            table_name=table_name,
            mask_keys=masks_keys,
            mask_to_annotate=mask_to_annotate,
            markers_to_quantify=quant.markers_to_quantify,
            overwrite=args.overwrite,
            add_qc_masks=quant.add_qc_masks,
            qc_prefix=qc_prefix,
        )

        quant_controller_list.append(controller)

    # define the cores for the analysis
    core_dir = settings.analysis_dir / "rois"
    path_list = [core_dir / f for f in os.listdir(core_dir)]
    path_list.sort()

    # run processing
    for sd_path in path_list:

        logger.info(f"Quantifying {sd_path.name}")

        # get sdata
        sdata = sd.read_zarr(sd_path)

        # run quantification
        for controller in quant_controller_list:
            controller.run(sdata)


if __name__ == "__main__":
    main()
