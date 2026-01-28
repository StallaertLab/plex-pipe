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
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://stallaertlab.github.io/plex-pipe/)

PlexPipe is a [modular pipeline](what_is_plexpipe.md) that transforms raw whole-slide multiplexed images into quantitative single-cell data. It accepts TIFF inputs following the CellDive convention (see [Input Data](usage/input_data.md)) and stores results as [SpatialData](https://spatialdata.scverse.org/en/latest/index.html) objects, enabling interactive exploration with the [Napari SpatialData Plugin](https://github.com/scverse/napari-spatialdata).

The pipeline can be executed via scripts or Jupyter notebooks (see [Execution Modes](usage/execution_modes.md)). For scalable parallel processing, use the Nextflow implementation: [plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow).
