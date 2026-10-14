"""Rebuild the test fixture ``ROI_001_crop.zarr`` from the example analysis.

The fixture is a small crop of ROI_001 from the example data run through the
pipeline (notebooks 01-05 or scripts 02/04/05 with
``examples/example_pipeline_config.yaml``). The crop covers the two QC
exclusion shapes drawn in notebook 03, so it holds images, labels, shapes and
the quantification table, written in the current SpatialData / Zarr format.

Run from the repository root after the example analysis has finished::

    python tests/example_data/make_fixture.py
"""

import shutil
from pathlib import Path

import spatialdata as sd

REPO = Path(__file__).parents[2]
SOURCE = REPO / "examples" / "output" / "sample_analysis" / "rois" / "ROI_001.zarr"
TARGET = Path(__file__).parent / "ROI_001_crop.zarr"

# Pixel window (x, y) around the QC exclusion shapes.
MIN_XY = [3100, 2200]
MAX_XY = [3900, 2800]


def main() -> None:
    """Crop the example ROI and write it as the test fixture."""
    sdata = sd.read_zarr(SOURCE)
    crop = sd.bounding_box_query(
        sdata,
        axes=("x", "y"),
        min_coordinate=MIN_XY,
        max_coordinate=MAX_XY,
        target_coordinate_system="global",
        filter_table=True,
    )
    if TARGET.exists():
        shutil.rmtree(TARGET)
    crop.write(TARGET)
    print(sd.read_zarr(TARGET))


if __name__ == "__main__":
    main()
