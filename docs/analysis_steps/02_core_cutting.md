# Core Cutting

**Goal:** Extract individual cores into separate SpatialData objects.

Once cores are defined, the pipeline extracts these regions from the original OME-TIFF files. This step handles complex **channel selection logic**, allowing you to exclude specific channels, or select the best version of a repeated marker.

*   **Input:** Raw OME-TIFF images and core coordinates.
*   **Output:** Individual **SpatialData** (Zarr) objects for each core (images only).

Parameters of this step are defined in the Core Cutting part of [configuration](../configuration/reference.md#core-cutting).
