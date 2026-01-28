# PlexPipe - Multiplexed Image Analysis Pipeline

<style>
  .logo-dark { display: none; }
  [data-md-color-scheme="slate"] .logo-light { display: none; }
  [data-md-color-scheme="slate"] .logo-dark { display: inline; }
</style>

![Logo](images/PlexPipe_logo_small.png){ .logo-light }
![Logo](images/PlexPipe_logo_small_dark_transparent.png){ .logo-dark }

[![Tests](https://github.com/StallaertLab/plex-pipe/actions/workflows/test_and_deploy.yaml/badge.svg)](https://github.com/StallaertLab/plex-pipe/actions)
[![codecov](https://codecov.io/github/StallaertLab/plex-pipe/graph/badge.svg?token=EI4L1DW720)](https://codecov.io/github/StallaertLab/plex-pipe)
![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-green)

## Overview

**PlexPipe** processes multiplexed images through a series of [modular steps](analysis_steps.md), transforming raw whole-slide TIFF images into quantitative single-cell data.

## Key Features

* **Input Data:** The pipeline accepts sets of individual TIFF files. It follows the naming conventions used by the **Cell DIVE** system. For specific requirements regarding file naming, refer to [Input Data](usage/input_data.md).
* **Remote Data Sourcing:** Seamlessly source and transfer large-scale imaging datasets from institutional endpoints or personal collections using [Globus](https://www.globus.org/). This ensures secure and reliable data movement directly into your processing environment (see: [Globus Integration](usage/globus.md)).
* **Data Integration:** Outputs are stored as [SpatialData](https://spatialdata.scverse.org/en/latest/index.html) objects, making them ready for downstream analysis within the scverse ecosystem or interactive exploration via the [napari-spatialdata plugin](https://github.com/scverse/napari-spatialdata).
* **Flexible Execution:** PlexPipe can be implemented in two ways based on your needs:
    * **Local/Interactive:** Utilize the provided Python scripts or Jupyter Notebooks for smaller datasets or pipeline prototyping (see [Execution Modes](usage/execution_modes.md)).
    * **High-Throughput:** For parallel processing and large-scale workflows, use the Nextflow-optimized version: [plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow).
