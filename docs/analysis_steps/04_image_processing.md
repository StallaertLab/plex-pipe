# Image Processing

**Goal:** Enhance images and segment objects.

This is a highly flexible stage defined by a list of [processors](../usage/processors.md) in the configuration. It supports:

*   **Image Filtering:** Operations like normalization, denoising, and computing means.
*   **Object Segmentation:** Using deep learning models (e.g., **Cellpose**, **InstanSeg**) to identify nuclei and cells.
*   **Mask Building:** Creating derivative masks, such as cytoplasmic rings or combining existing masks via boolean operations.

*   **Input:** Core SpatialData objects.
*   **Output:** SpatialData objects containing requested derivative images and masks.

The new elements can be requested to persist within the SpatialData object or be created temporarily as an intermediate step (e.g. normalized signal images can be created to use as the input for the segmentation step but not stored permanently).

Parameters of this step are defined in the Image Processing part of [configuration](../configuration/reference.md#image-processing).
