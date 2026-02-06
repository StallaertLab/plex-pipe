# Analysis Steps

PlexPipe processes multiplexed images through a series of modular steps, transforming raw whole-slide images into quantitative single-cell data.

To run the pipeline, users must prepare a [configuration file](../configuration/reference.md) that contains parameters for all the steps of the pipeline.


Note that Step 1 (ROI Definition) and Step 3 (Quality Control) require manual interaction through the Napari viewer interface.d

---

## 1. [ROI Definition](01_roi_definition.md)

**Goal:** Identify the boundaries of Region of Interest (ROI) within a whole-slide image.

*   **Input:** A representative whole-slide image (usually DAPI).
*   **Output:** A list of ROIs coordinates and their visual representation.

---

## 2. [ROI Cutting](02_core_cutting.md)

**Goal:** Extract individual ROIs into separate SpatialData objects.

*   **Input:** Raw OME-TIFF images and ROI coordinates.
*   **Output:** Individual **SpatialData** (Zarr) objects for each ROI (images only).

---

## 3. [Quality Control (QC)](03_quality_control.md)

**Goal:** Define image areas from which objects should be excluded (e.g. imaging artefacts, folded tissue, etc.).

*   **Input:** SpatialData objects containing marker images.
*   **Output:** User-defined exclusion shapes (added to SpatialData objects).

---

## 4. [Image Processing](04_image_processing.md)

**Goal:** Enhance images and segment objects.

*   **Input:** Core SpatialData objects.
*   **Output:** SpatialData objects containing requested derivative images and masks.

---

## 5. [Quantification](05_quantification.md)

**Goal:** Generate single-cell quantitative data.

*   **Input:** SpatialData objects containing Segmentation masks and intensity images.
*   **Output:** AnnData tables containing single-cell feature matrices added to SpatialData objects.
