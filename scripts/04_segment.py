import argparse
import sys
from datetime import datetime

from loguru import logger

from plex_pipe.config.config_loaders import load_config, save_config_snapshot
from plex_pipe.io.filesystem import list_roi_stores
from plex_pipe.runners import build_resource_controllers, segment_roi


def configure_logging(settings):
    """
    Setup logging.
    """

    log_file = (
        settings.log_dir_path
        / f"cores_segmentation_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    )

    logger.remove()
    logger.add(sys.stdout, level="DEBUG")
    logger.add(log_file, level="DEBUG", enqueue=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Segment ROIS using the provided config file."
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
    logger.info("Starting object segmentation script.")
    save_config_snapshot(settings)

    # setup builders of additional data elements
    builders_list = build_resource_controllers(settings, overwrite=args.overwrite)

    # run processing
    for sd_path in list_roi_stores(settings.roi_dir_output_path):

        logger.info(f"Processing {sd_path.name}")
        segment_roi(settings, sd_path, builders_list)


if __name__ == "__main__":
    main()
