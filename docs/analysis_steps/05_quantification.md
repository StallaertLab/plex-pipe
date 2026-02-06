# Quantification

**Goal:** Generate single-cell quantitative data.

The final step extracts features from the segmented objects. It calculates:
*   **Morphological Properties:** e.g. Area, centroid, eccentricity, etc.
*   **Intensity Properties:** e.g. Mean, median expression levels for specified markers.

The AnnData table can be linked to a selected mask in the SpatialData object.
If several masks are specified to be quantified in this step the results will be stored in a single AnnData table and can be attached to a single segmentation mask (e.g. AnnData storing measuremnt for the cell and the nucleus regions will be linked to the cell segmentation mask).
If measurements should be linked to their corresponding masks, please specify separate quantification groups to create separate AnnData tables and link them to their matching masks.
Both of the above approaches are valid and subject to the user preference.

The results are stored as **AnnData** tables within the SpatialData object, linking spatial locations to quantitative profiles for downstream analysis.

*   **Input:** SpatialData objects containing Segmentation masks and intensity images.
*   **Output:** AnnData tables containing single-cell feature matrices added to SpatialData objects.

Parameters of this step are defined in the Quantification part of [configuration](../configuration/reference.md#quantification).
