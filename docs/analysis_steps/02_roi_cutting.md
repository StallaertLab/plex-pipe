# ROI Cutting

## Overview

Once ROIs are defined, the pipeline extracts these regions from the original TIF(F) files.
This step handles [channel selection logic](../configuration/channel-selection.md), allowing you to exclude specific channels, or select the best version of a repeated marker.

*   **Input:** TIF(F) images and ROI coordinates (`rois.pkl`).
*   **Output:** Individual **SpatialData** (Zarr) objects for each ROI (images only).

Parameters of this step are defined in the ROI Cutting part of the [config file](../configuration/reference.md#core-cutting).

---
## Data Sourcing

This module supports dual modes of operation for data retrieval: **Local** and [**Globus**](https://www.globus.org/). For comprehensive instructions on configuring Globus for remote data sourcing, see [Globus Settings](../usage/globus.md) documentation and the corresponding [demonstration notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/extras/02_roi_cutting_globus_demo.ipynb).

---
## Execution

This module is fully parameterized via the [configuration file](../configuration/reference.md#core-cutting) and does not require manual intervention.
Consequently, it can be executed via a Jupyter Notebook, standalone script, or as a component of the Nextflow pipeline; further details are available in the [Execution Modes](../usage/execution_modes.md) documentation.

---
## Notebook workflow

The example [Jupyter Notebook](https://github.com/StallaertLab/plex-pipe/blob/main/notebooks/02_roi_cutting_demo.ipynb) demonstrates the execution workflow using locally available data.

To complete the process, execute the following sections sequentially:

* **Read in config**: Specify the pathway to the analysis configuration file and load the required settings.
* **Define the logger**: Initialize the logging protocol to track execution progress and document the process.
* **Define ROIs for processing**: Ingests the [ROI parameters](./01_roi_definition.md/#roi-output-schema) into a Pandas DataFrame. A demonstration cell is provided to truncate this DataFrame for rapid testing purposes.
* **Discover signal channels**: Identifies available TIFF images and implements the [channel selection logic](../configuration/channel-selection.md). A demonstration cell is included to show how to subset the channel list for testing.
* **Run ROI cutting**: Triggers the ROI extraction process utilizing the local file sourcing strategy.

## Script execution
