"""Step 1, ROI definition: draw the ROIs in napari.

Opens the detection image named in the config with the ROI widget. Draw or
edit the ROIs, click "Save ROIs", then close the napari window to finish:

    python 01_define_rois.py --exp_config ../examples/example_pipeline_config.yaml
"""

import argparse
import sys
from datetime import datetime

import napari
from loguru import logger

from plex_pipe.config.config_loaders import load_config
from plex_pipe.ui import RoiWidget


def configure_logging(settings):
    """Also log to a file in the analysis log folder (DEBUG level)."""
    log_file = (
        settings.log_dir_path / f"roi_definition_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    )
    logger.add(log_file, level="DEBUG", enqueue=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Draw the ROIs in napari (step 1). Close the window to finish."
    )
    parser.add_argument(
        "--exp_config", help="Path to experiment YAML config.", required=True
    )
    return parser.parse_args()


def modified_time(path):
    """Modification time of ``path``, or None if it does not exist."""
    return path.stat().st_mtime if path.exists() else None


def main():
    args = parse_args()
    # Console logging from the start; the log file is added once the config is loaded.
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    settings = load_config(args.exp_config)
    configure_logging(settings)

    roi_file = settings.roi_info_file_path
    before = modified_time(roi_file)
    logger.info(f"ROI table: {roi_file}")
    logger.info("Draw or edit the ROIs, click 'Save ROIs', then close the window.")

    viewer = napari.Viewer(title="PlexPipe: ROI definition")
    roi_widget = RoiWidget.from_config(viewer, settings)
    viewer.window.add_dock_widget(roi_widget, area="left")
    napari.run()  # returns when the window is closed

    if modified_time(roi_file) in (None, before):
        logger.warning(f"Window closed without saving: {roi_file} was not changed.")
    else:
        logger.info(f"ROIs saved to {roi_file}.")


if __name__ == "__main__":
    main()
