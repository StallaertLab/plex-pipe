import argparse
import sys
from datetime import datetime

from loguru import logger

from plex_pipe.config.config_loaders import load_config, save_config_snapshot
from plex_pipe.io.filesystem import list_roi_stores
from plex_pipe.runners import build_quant_controllers, quantify_roi


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
    settings = load_config(args.exp_config)

    # setup logging
    configure_logging(settings)
    logger.info("Starting quantification script.")
    save_config_snapshot(settings)

    # setup quantification controllers
    # (the same controllers are used for all ROIs, so all tables have the
    # same columns)
    quant_controller_list = build_quant_controllers(settings, overwrite=args.overwrite)

    # run processing
    for sd_path in list_roi_stores(settings.roi_dir_output_path):

        logger.info(f"Quantifying {sd_path.name}")
        quantify_roi(sd_path, quant_controller_list)


if __name__ == "__main__":
    main()
