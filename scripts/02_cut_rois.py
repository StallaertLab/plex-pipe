import argparse
import sys
from datetime import datetime

import pandas as pd
from loguru import logger

from plex_pipe.core_cutting.controller import (
    CorePreparationController,
)
from plex_pipe.core_cutting.input_strategy import (
    GlobusFileStrategy,
    LocalFileStrategy,
)
from plex_pipe.utils.config_loaders import load_analysis_settings
from plex_pipe.utils.globus_utils import GlobusConfig


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
        default="r_collection_id",
    )
    parser.add_argument(
        "--to_collection",
        help="Key for destination collection in Globus config.",
        default="crcd_collection_id",
    )
    parser.add_argument(
        "--cleanup",
        "-c",
        action="store_true",
        help="Enable deletion of Globus transfered image files.",
    )

    return parser.parse_args()


def main():

    args = parse_args()

    # read config file
    config = load_analysis_settings(args.exp_config)

    # setup logging
    configure_logging(config)
    logger.info("Starting core cutting script.")

    # setup Globus if requested
    if args.globus_config:

        gc = GlobusConfig.from_yaml(
            args.globus_config,
            source_key=args.from_collection,
            dest_key=args.to_collection,
        )

    else:

        gc = None

    # get cores coordinates
    df_path = config.roi_info_file_path
    df = pd.read_pickle(df_path)

    # define file access
    if gc:
        # initialize Globus transfer
        strategy = GlobusFileStrategy(
            config=config, gc=gc, cleanup_enabled=args.cleanup
        )
        strategy.submit_all_transfers(batch_size=1)
    else:
        strategy = LocalFileStrategy(config=config)

    # setup cutting controller
    controller = CorePreparationController(
        metadata_df=df,  # df defines which cores to process
        file_strategy=strategy,
        temp_dir=config.roi_dir_tif_path,
        output_dir=config.roi_dir_output_path,
        margin=config.roi_cutting.margin,
        mask_value=config.roi_cutting.mask_value,
        max_pyramid_levels=config.sdata_storage.max_pyramid_level,
        chunk_size=config.sdata_storage.chunk_size,
        downscale=config.sdata_storage.downscale,
    )

    # run core cutting
    controller.run()


if __name__ == "__main__":
    main()
