# PlexPipe

[![Tests](https://github.com/StallaertLab/plex-pipe/actions/workflows/test_and_deploy.yaml/badge.svg)](https://github.com/StallaertLab/plex-pipe/actions)
[![codecov](https://codecov.io/github/StallaertLab/plex-pipe/graph/badge.svg?token=EI4L1DW720)](https://codecov.io/github/StallaertLab/plex-pipe)
![Python Versions](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-green)
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://stallaertlab.github.io/plex-pipe/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/images/PlexPipe_logo_small_dark_transparent.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/images/PlexPipe_logo_small.png">
  <img alt="Logo" src="./docs/images/PlexPipe_logo_small.png">
</picture>


**PlexPipe turns raw multiplexed whole-slide images into quantitative single-cell data.** It starts from a set of individual TIFF files, typically one per marker, reading the information it needs from their file names. The images are expected to be analysis-ready, already stitched and background-corrected, so PlexPipe concentrates on everything downstream: outlining regions of interest, segmenting cells, and producing a single-cell feature table ready for the [scverse](https://scverse.org/) ecosystem.

PlexPipe runs one step at a time, each driven by a single configuration file that holds the parameters for the whole workflow. Two steps, ROI definition and quality control, open a [napari](https://napari.org/) viewer, because they need a person to outline the regions of interest and mark imaging artefacts for exclusion.

## The pipeline

Five stages, each demonstrated by a notebook in `notebooks/`:

1. **ROI definition** (interactive): find and outline the regions of interest in a whole-slide image, for example dearraying the cores of a tissue microarray. Notebook: `01_roi_definition_demo.ipynb`.
2. **ROI cutting:** extract each ROI into its own [SpatialData](https://spatialdata.scverse.org/) object. Notebook: `02_roi_cutting_demo.ipynb`.
3. **Quality control** (interactive): mark imaging artefacts and tissue to exclude from analysis. Notebook: `03_QC_demo.ipynb`.
4. **Segmentation:** enhance images and segment cells and nuclei into masks (Cellpose or InstanSeg). Notebook: `04_segmentation_demo.ipynb`.
5. **Quantification:** measure per-cell marker intensities into an AnnData table. Notebook: `05_quantification_demo.ipynb`.

Outputs are stored as SpatialData (Zarr) objects with AnnData tables, so results drop straight into scverse tools or the [napari-spatialdata](https://github.com/scverse/napari-spatialdata) plugin for interactive exploration.

## Installation

PlexPipe uses [uv](https://docs.astral.sh/uv/) for environment management. To run the notebooks, clone the repository and sync the full environment:

```bash
git clone https://github.com/StallaertLab/plex-pipe.git
cd plex-pipe
uv sync --extra all
```

`--extra all` installs every optional feature: the segmentation backends (Cellpose, InstanSeg, PyTorch), the napari GUI, Jupyter, and Globus transfer. On an NVIDIA machine you need a CUDA build of PyTorch, and on Windows there are a couple of extra notes, both covered in the [installation guide](https://stallaertlab.github.io/plex-pipe/usage/installation/). To use PlexPipe as a library in your own scripts rather than running the notebooks, that guide also has an import-only setup.

## Try it on example data

The notebooks run on a small example dataset, and the first notebook downloads it for you with `fetch_example()`, so you can go from a fresh clone to a running pipeline without hunting for data. 

Start with `01_roi_definition_demo.ipynb` and work through to `05`. Stages 1 and 3 open a napari window for the interactive steps; the rest run automatically from the shared configuration file.

## Execution modes

For smaller datasets and prototyping, run the notebooks or standalone scripts locally. For large-scale parallel processing on HPC, use the Nextflow version, [plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow).


## Documentation

Full documentation is available at:  [![Docs](https://img.shields.io/badge/docs-online-blue)](https://stallaertlab.github.io/plex-pipe/)

## Status

PlexPipe is in active development (alpha). Interfaces and the configuration schema may still change before a 1.0 release. Bug reports and feedback are welcome on the [issue tracker](https://github.com/StallaertLab/plex-pipe/issues).

## Similar projects

PlexPipe is one of several open pipelines for turning multiplexed images into single-cell data:

- [MCMICRO](https://mcmicro.org/) 
- [Harpy](https://github.com/saeyslab/harpy)
- [Sopa](https://prism-oncology.github.io/sopa/)
- [Spatialproteomics](https://github.com/sagar87/spatialproteomics)


PlexPipe's distinguishing emphasis is human-in-the-loop interaction. Two of its five steps, ROI definition and quality control, open a napari viewer so a scientist can outline regions of interest and annotate imaging artefacts directly, keeping expert judgement at the points in the workflow where it matters most.

## License

Distributed under the terms of the BSD-3-Clause license.
