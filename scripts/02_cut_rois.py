import argparse
import sys
from datetime import datetime

from loguru import logger

from plex_pipe.config.config_loaders import load_config, save_config_snapshot
from plex_pipe.io.globus import GlobusConfig
from plex_pipe.runners import cleanup_setting, prepare_rois
from plex_pipe.stages.roi_preparation.file_strategy import (
    GlobusFileStrategy,
    LocalFileStrategy,
)


def configure_logging(config):
    """
    Setup logging.
    """

    log_file = (
        config.log_dir_path / f"cores_cutting_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    )

    logger.remove()
    logger.add(sys.stdout, level="INFO")
    logger.add(log_file, level="DEBUG", enqueue=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare cores from OME-TIFFs using metadata and optional Globus transfers."
    )

    parser.add_argument(
        "--exp_config", help="Path to experiment YAML config.", required=True
    )
    parser.add_argument("--globus_config", help="Path to Globus config.")

    parser.add_argument(
        "--from_collection",
        help="Key for source collection in Globus config.",
        default="remote_source",
    )
    parser.add_argument(
        "--to_collection",
        help="Key for destination collection in Globus config.",
        default="local_workstation",
    )
    parser.add_argument(
        "--cleanup",
        "-c",
        action="store_true",
        help="Delete each image transferred via Globus once its ROIs are cut.",
    )
    parser.add_argument(
        "--roi_cleanup",
        action="store_true",
        help="Delete the per-ROI TIFFs once each ROI is assembled.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    # read config file
    config = load_config(args.exp_config)

    # setup logging
    configure_logging(config)
    logger.info("Starting core cutting script.")
    save_config_snapshot(config)

    # setup Globus if requested
    if args.globus_config:

        gc = GlobusConfig.from_yaml(
            args.globus_config,
            source_key=args.from_collection,
            dest_key=args.to_collection,
        )

    else:

        gc = None

    # define file access
    if gc:
        # initialize Globus transfer
        strategy = GlobusFileStrategy(
            config=config,
            gc=gc,
            cleanup_enabled=cleanup_setting(
                "cleanup", args.cleanup, config.roi_cutting.transfer_cleanup_enabled
            ),
        )
        strategy.submit_all_transfers(batch_size=1)
    else:
        strategy = LocalFileStrategy(config=config)

    # cut and assemble all ROIs
    prepare_rois(config, strategy, roi_cleanup=args.roi_cleanup).run()


if __name__ == "__main__":
    main()
