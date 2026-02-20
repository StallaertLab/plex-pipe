# Quantification

## Overview

The final step extracts features from the segmented objects and stores them in the `AnnData` table(s) within `SpatialData` objects.

*   **Input:** `SpatialData` objects containing segmentation masks and intensity images.
*   **Output:** `AnnData` tables containing single-cell feature matrices added to `SpatialData` objects.

Parameters of this step are defined in the Quantification part of [configuration](../configuration/reference.md#quantification).

---
## Supported features

* **Morphological Features:** Geometric attributes such as area, centroid, eccentricity, and orientation. All [skimage.measure.regionprops](https://scikit-image.org/docs/0.25.x/api/skimage.measure.html#skimage.measure.regionprops) properties are supported.
* **Intensity Features:** Statistical summaries (e.g., mean or median expression) for specified markers across the masked regions.

<!-- METRICS_START -->


| Feature Name | Source / Implementation | Description |
| :--- | :--- | :--- |
| **mean** | Skimage: `mean_intensity` | Standard intensity property from `skimage.measure.regionprops`. |
| **max** | Skimage: `max_intensity` | Standard intensity property from `skimage.measure.regionprops`. |
| **min** | Skimage: `min_intensity` | Standard intensity property from `skimage.measure.regionprops`. |
| **median** | Custom: `calculate_median` | Calculates the median intensity of the region. |
| **sum** | Custom: `calculate_sum` | Calculates the sum intensity of the region. |
| **std** | Custom: `calculate_std` | Calculates the standard deviation of intensity of the region. |

<!-- METRICS_END -->

---

## Linking AnnData Tables to Segmentation Masks

In the `SpatialData` framework, every table should ideally be linked to a set of regions (masks).
You can choose between two primary organizational strategies:

### Option 1: Distributed Tables (Matching Links)
Separate **quantification groups** are defined to create distinct AnnData tables for each mask.
* **Example:** A "cell" table linked to the cell mask and a "nucleus" table linked to the nucleus mask.
* **Benefit:** Provides a strict 1:1 mapping between the table rows and the spatial labels.

### Option 2: Consolidated Table (Single Link)
Results from multiple masks are stored in a **single AnnData table**.
* **Example:** Measurements for both "cell" and "nucleus" regions are stored in one table and linked to the "cell" segmentation mask.
* **Benefit:** Simplifies downstream analysis by keeping all properties of a biological cell in one place.

Both approaches are supported; choose the one that best fits your downstream analysis workflow.

---
{% include "includes/execution_snippet.md" %}

---
## Notebook workflow

The example [Jupyter Notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/05_quantification_demo.ipynb) demonstrates the execution workflow using locally available data.

To complete the process, execute the following sections sequentially:

* **Read in config**: Specify the path to the analysis configuration file and load the required settings.
* **Specify the overwriting strategy**: Set the `OVERWRITE_FLAG`. If `False`, the pipeline will throw an error to prevent overwriting existing table. If `True`, existing table will be replaced. Use with caution!
* **Define the logger**: Initialize the logging protocol to track execution progress and document the processing steps.
* **Define ROIs for processing**: Identify the `SpatialData` objects to be processed. A demonstration cell is provided to truncate this list for faster testing.
* **Setup quantifiers**: Initialize the quantifying objects defined in your configuration. These objects are created once and reused across all ROIs.
* **Run ROIs Quantification**: Quantify the ROIs.

---

## Script execution

```bash
python 05_quantify.py --exp_config ../examples/example_pipeline_config.yaml --overwrite
```
