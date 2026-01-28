# Analysis Steps

PlexPipe processes multiplexed images through a series of modular steps, transforming raw whole-slide images into quantitative single-cell data.

---

## 1. Core Detection

**Goal:** Identify and define the boundaries of tissue cores within a whole-slide image.

This step is supported by a small napari widget operated from a Jupyter [notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/00_core_definition_demo.ipynb) that allows for the definition of the tissue regions that should be analyzed as separate entities.
Stemming from the TMA (Tissue Microarray) these tissue regions will be referred to as cores.
The cores are defined manually within a napari window or automatically using a **Segment Anything Model 2 (SAM2)** to automatically detect tissue cores on a specified detection image (e.g., DAPI).
(There is a set of settings that can be specified in the config file to support detection with SAM )

SAM2 is not really supported on Windows but it's possible to set it up on the Linux subsystem for Linux. If the widget is used on Windows the segmentation through SAM2 will be executed as a subprocess, you need to provide a path to the linux-based python environment with installed SAM2.

*   **Input:** A representative whole-slide image (usually DAPI).
*   **Output:** A list of core coordinates (csv). Example cores definition file can be found in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples).

Parameters of this step are defined in the Core Detection part of [configuration](configuration/config_overview.md#core-detection).

---

## 2. Core Cutting

**Goal:** Extract individual cores into separate SpatialData objects.

Once cores are defined, the pipeline extracts these regions from the original OME-TIFF files. This step handles complex **channel selection logic**, allowing you to exclude specific channels, or select the best version of a repeated marker.

*   **Input:** Raw OME-TIFF images and core coordinates.
*   **Output:** Individual **SpatialData** (Zarr) objects for each core (images only).

Parameters of this step are defined in the Core Cutting part of [configuration](configuration/config_overview.md#core-cutting).

---

## 3. Quality Control (QC)

**Goal:** Define image areas from which objects should be excluded (e.g. imaging artefacts, folded tissue, etc.).

This is a manual step performed by user drawing exclusion shapes.
To support it we provide a napari widget that can be easily operated from a Jupyter [notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/04_QC_demo.ipynb)

Specified polygons will be used in the quantification step to create masks in the AnnData tables marking if an intensity-based properties for a given channel/marker should be considered as valid in the downstream analysis.

*   **Input:** SpatialData objects containing marker images.
*   **Output:** User-defined exclusion shapes (added to SpatialData objects).

Parameters of this step are defined in the Quality Control (QC) part of [configuration](configuration/config_overview.md#quality-control).

---

## 4. Image Processing

**Goal:** Enhance images and segment objects.

This is a highly flexible stage defined by a list of [processors](./usage/processors.md) in the configuration. It supports:

*   **Image Filtering:** Operations like normalization, denoising, and computing means.
*   **Object Segmentation:** Using deep learning models (e.g., **Cellpose**, **InstanSeg**) to identify nuclei and cells.
*   **Mask Building:** Creating derivative masks, such as cytoplasmic rings or combining existing masks via boolean operations.

*   **Input:** Core SpatialData objects.
*   **Output:** SpatialData objects containing requested derivative images and masks.

The new elements can be requested to persist within the SpatialData object or be created temporarily as an intermediate step (e.g. normalized signal images can be created to use as the input for the segmentation step but not stored permanently).

Parameters of this step are defined in the Image Processing part of [configuration](configuration/config_overview.md#image-processing).

---

## 5. Quantification

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

Parameters of this step are defined in the Quantification part of [configuration](configuration/config_overview.md#quantification).
