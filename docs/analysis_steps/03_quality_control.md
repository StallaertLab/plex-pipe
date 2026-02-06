# Quality Control (QC)

**Goal:** Define image areas from which objects should be excluded (e.g. imaging artefacts, folded tissue, etc.).

This is a manual step performed by user drawing exclusion shapes.
To support it we provide a napari widget that can be easily operated from a Jupyter [notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/04_QC_demo.ipynb)

Specified polygons will be used in the quantification step to create masks in the AnnData tables marking if an intensity-based properties for a given channel/marker should be considered as valid in the downstream analysis.

*   **Input:** SpatialData objects containing marker images.
*   **Output:** User-defined exclusion shapes (added to SpatialData objects).

Parameters of this step are defined in the Quality Control (QC) part of [configuration](../configuration/reference.md#quality-control).
