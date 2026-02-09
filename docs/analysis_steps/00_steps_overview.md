# Analysis Steps

PlexPipe processes multiplexed whole-slide images through a sequence of modular steps, transforming raw imaging data into quantitative single-cell measurements.

To run the pipeline, users must first create a [configuration file](../configuration/config_overview.md) that defines the parameters for all pipeline steps. This configuration file is the central control point for PlexPipe and is required throughout the entire workflow.

While most steps run automatically based on the configuration, Step 1 (ROI Definition) and Step 3 (Quality Control) require user interaction via the Napari viewer.
In these steps, users manually inspect the data, define regions of interest, and annotate imaging artefacts.

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

**Goal:** Enhance images, segment objects and create derivative masks.

*   **Input:** Core SpatialData objects.
*   **Output:** SpatialData objects containing requested derivative images and masks.

---

## 5. [Quantification](05_quantification.md)

**Goal:** Generate single-cell quantitative data.

*   **Input:** SpatialData objects containing Segmentation masks and intensity images.
*   **Output:** AnnData tables containing single-cell feature matrices added to SpatialData objects.
