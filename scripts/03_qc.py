"""Step 3, quality control: mark imaging artefacts per marker in napari.

Opens one napari window per ROI with the QC widget. Draw exclusion shapes for
the markers that need them, click "Save All", then close the window; the next
ROI opens. Use --roi to review a single ROI:

    python 03_qc.py --exp_config ../examples/example_pipeline_config.yaml
    python 03_qc.py --exp_config ../examples/example_pipeline_config.yaml --roi ROI_001

Stop early with Ctrl+C in the terminal; ROIs already saved keep their shapes.
"""

import argparse
import sys
from datetime import datetime

import napari
import spatialdata as sd
from loguru import logger

from plex_pipe.config.config_loaders import load_config
from plex_pipe.io.filesystem import list_roi_stores
from plex_pipe.ui import QCWidget


def configure_logging(settings):
    """Log to the console and to a file in the analysis log folder."""
    log_file = settings.log_dir_path / f"qc_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    logger.add(log_file, level="DEBUG", enqueue=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mark QC exclusion shapes in napari (step 3), one ROI at a time."
    )
    parser.add_argument(
        "--exp_config", help="Path to experiment YAML config.", required=True
    )
    parser.add_argument("--roi", help="Review only this ROI (e.g. ROI_001).")
    return parser.parse_args()


def main():
    args = parse_args()
    settings = load_config(args.exp_config)
    configure_logging(settings)

    stores = list_roi_stores(settings.roi_dir_output_path)
    if args.roi:
        names = [s.stem for s in stores]
        stores = [s for s in stores if s.stem == args.roi]
        if not stores:
            sys.exit(f"ROI '{args.roi}' not found. Available: {', '.join(names)}")
    if not stores:
        sys.exit(f"No ROI stores in {settings.roi_dir_output_path}; run step 2 first.")

    logger.info(
        "For each ROI: draw exclusion shapes, click 'Save All', close the window."
    )
    for i, store in enumerate(stores, start=1):
        logger.info(f"QC {i}/{len(stores)}: {store.stem}")
        sdata = sd.read_zarr(store)
        viewer = napari.Viewer(title=f"PlexPipe QC: {store.stem} ({i}/{len(stores)})")
        qc_widget = QCWidget(viewer, sdata)
        viewer.window.add_dock_widget(qc_widget, area="right")
        napari.run()  # returns when the window is closed

    logger.info("QC finished.")


if __name__ == "__main__":
    main()
