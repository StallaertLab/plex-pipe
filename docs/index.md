# PlexPipe - Multiplexed Image Analysis Pipeline

<style>
  .logo-dark { display: none; }
  [data-md-color-scheme="slate"] .logo-light { display: none; }
  [data-md-color-scheme="slate"] .logo-dark { display: inline; }
</style>

![Logo](images/PlexPipe_logo_small.png){ .logo-light }
![Logo](images/PlexPipe_logo_small_dark_transparent.png){ .logo-dark }

[![Tests](https://github.com/plexpipe/plex-pipe/actions/workflows/test_and_deploy.yaml/badge.svg)](https://github.com/plexpipe/plex-pipe/actions)
[![codecov](https://codecov.io/gh/plexpipe/plex-pipe/graph/badge.svg)](https://codecov.io/github/plexpipe/plex-pipe)
![Python Versions](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-green)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23425779.svg)](https://doi.org/10.5281/zenodo.23425779)

## Overview

**PlexPipe** is a multiplex analysis pipeline that processes images through a series of [modular steps](./analysis_steps/00_steps_overview.md), transforming raw whole-slide TIFF images into quantitative single-cell data.

## Key Features

* **Input Data:** The pipeline accepts sets of individual TIFF files, one per channel. Marker names and imaging rounds are read from **Cell DIVE** file names, or from a channel manifest CSV for data from any other platform (see [Input Data](usage/input_data.md) and [Channel Selection](configuration/channel-selection.md)).
* **Remote Data Sourcing:** Seamlessly source and transfer large-scale imaging datasets from institutional endpoints or personal collections using [Globus](https://www.globus.org/). This ensures secure and reliable data movement directly into your processing environment (see: [Globus Integration](usage/globus.md)).
* **Data Integration:** Outputs are stored as [SpatialData](https://spatialdata.scverse.org/en/latest/index.html) objects, making them ready for downstream analysis within the [scverse](https://scverse.org/) ecosystem or interactive exploration via the [napari-spatialdata plugin](https://github.com/scverse/napari-spatialdata).
* **Flexible Execution:** PlexPipe can be implemented in two ways based on your needs:
    * **Local/Interactive:** Utilize the provided Python scripts or Jupyter Notebooks for smaller datasets or pipeline prototyping (see [Execution Modes](usage/execution_modes.md)).
    * **High-Throughput:** For parallel processing and large-scale workflows, use the Nextflow-optimized version: [plex-pipe-nextflow](https://github.com/plexpipe/plex-pipe-nextflow).

## Used in

* Yang Y, Bukkuri A, Poe D, McLaughlin J, Hao S, Brown DD, Kedziora KM, Stallaert W. Distinct p21 dynamics drive alternative routes to whole-genome duplication through a common CDK4/6-dependent polyploid G0 state. *bioRxiv* [Preprint]. 2026 Jan 15:2026.01.15.699545. doi: [10.64898/2026.01.15.699545](https://doi.org/10.64898/2026.01.15.699545). PMID: 41648389; PMCID: PMC12871375.
