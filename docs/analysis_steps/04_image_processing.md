
# Image Processing

## Overview

The Image Processing step is a highly flexible stage of the PlexPipe workflow, defined by an ordered list of [processors](../usage/processors.md) specified in the configuration file. Each processor operates on image or mask data and can generate new derivative elements.

- **Input:** Core `SpatialData` objects.
- **Output:** `SpatialData` objects augmented with derived images and/or masks.

This step supports the following categories of operations:

- **Image Filtering**
  Intensity-based transformations such as normalization, denoising, smoothing, and computation of summary images (e.g. mean or maximum projections).

- **Object Segmentation**
  Identification of nuclei and cells using deep-learning–based segmentation models.
  Currently supported models include [**Cellpose**](https://www.cellpose.org/) and [**InstanSeg**](https://github.com/instanseg/instanseg).

- **Mask Building**
  Construction of derived masks, such as cytoplasmic rings using boolean operations.

All parameters controlling this step are defined in the *Image Processing* section of the [configuration reference](../configuration/reference.md#image-processing).

---

## Persistence

Newly generated images and masks can either be stored permanently within the `SpatialData` object or created only as temporary intermediates.

Temporary outputs are useful for multi-step workflows—for example, normalized intensity images may be generated solely to serve as input for a segmentation processor without being persisted in the final dataset.

---
## Execution

This module is fully parameterized via the [configuration file](../configuration/reference.md#image-processing) and does not require manual intervention.
Consequently, it can be executed via a Jupyter Notebook, standalone script, or as a component of the Nextflow pipeline; further details are available in the [Execution Modes](../usage/execution_modes.md) documentation.

---
## Notebook workflow

The example [Jupyter Notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/04_segmentation_demo.ipynb) demonstrates the execution workflow using locally available data.

To complete the process, execute the following sections sequentially:

* **Read in config**: Specify the path to the analysis configuration file and load the required settings.
* **Specify the overwriting strategy**: Set the `OVERWRITE_FLAG`. If `False`, the pipeline will throw an error to prevent overwriting existing resources. If `True`, existing resources will be replaced. Use with caution!
* **Define the logger**: Initialize the logging protocol to track execution progress and document the processing steps.
* **Define ROIs for processing**: Identify the `SpatialData` objects to be processed. A demonstration cell is provided to truncate this list for faster testing.
* **Setup processors**: Initialize the processing objects defined in your configuration. These objects are created once and reused across all ROIs.
* **Run ROI Processing**: Execute the list of processing steps for each ROI. Note that the pipeline automatically validates each `SpatialData` object immediately before it is processed. An optional validation cell is also provided to run this check for all objects in the list upfront, ensuring every ROI has the required components before starting the full execution.

---

## Script execution

```bash
python 04_segment.py --exp_config ../examples/example_pipeline_config.yaml --overwrite
```
