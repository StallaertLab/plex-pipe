# Analysis Steps

PlexPipe processes multiplexed images through a series of modular steps, transforming raw whole-slide images into quantitative single-cell data.

## 1. Core Detection

**Goal:** Identify and define the boundaries of tissue cores within a whole-slide image.

This step uses the **Segment Anything Model 2 (SAM2)** to automatically detect tissue cores on a specified detection image (e.g., DAPI). The pipeline analyzes the image pyramid to find regions of interest, filtering them based on area, intensity, and stability scores.

*   **Input:** A representative whole-slide image (usually DAPI).
*   **Output:** A list of core coordinates and masks.

## 2. Core Cutting

**Goal:** Extract individual cores into manageable, independent datasets.

Once cores are defined, the pipeline extracts these regions from the original OME-TIFF files. This step handles complex **channel selection logic**, allowing you to merge markers from different imaging rounds, exclude specific channels, or select the best version of a repeated marker.

*   **Input:** Raw OME-TIFF images and core coordinates.
*   **Output:** Individual **SpatialData** (Zarr) objects for each core.

## 3. Image Processing

**Goal:** Enhance images and segment biological objects.

This is a highly flexible stage defined by a list of processors in the configuration. It supports:

*   **Image Filtering:** Operations like normalization, denoising, and computing means.
*   **Object Segmentation:** Using deep learning models (e.g., **Cellpose**, **InstanSeg**) to identify nuclei and cells.
*   **Mask Building:** Creating derivative masks, such as cytoplasmic rings or combining existing masks via boolean operations.

*   **Input:** Core SpatialData objects.
*   **Output:** Processed image layers and segmentation labels stored within the SpatialData object.

## 4. Quality Control (QC)

**Goal:** Exclude artifacts and ensure data quality.

The pipeline integrates manual QC by recognizing exclusion shapes drawn by users (e.g., in Napari). Regions marked with specific prefixes (e.g., `qc_exclude`) are used to mask out cells or areas that should not be quantified, such as folded tissue or debris.

*   **Input:** User-defined exclusion shapes.
*   **Output:** Masked regions to be ignored during quantification.

## 5. Quantification

**Goal:** Generate single-cell quantitative data.

The final step extracts features from the segmented objects. It calculates:
*   **Morphological Properties:** Area, centroid, eccentricity, etc.
*   **Intensity Properties:** Mean, median, min, max expression levels for specified markers.

The results are stored as **AnnData** tables within the SpatialData object, linking spatial locations to quantitative profiles for downstream analysis.

*   **Input:** Segmentation masks and intensity images.
*   **Output:** AnnData tables containing single-cell feature matrices.
