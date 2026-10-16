# PlexPipe

[![Tests](https://github.com/plexpipe/plex-pipe/actions/workflows/test_and_deploy.yaml/badge.svg?branch=main)](https://github.com/plexpipe/plex-pipe/actions)
[![codecov](https://codecov.io/gh/plexpipe/plex-pipe/graph/badge.svg)](https://codecov.io/github/plexpipe/plex-pipe)
![Python Versions](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-green)
[![Docs](https://img.shields.io/badge/docs-online-blue)](https://plexpipe.github.io/plex-pipe/)
[![PyPI](https://img.shields.io/pypi/v/plex-pipe)](https://pypi.org/project/plex-pipe/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue)](https://github.com/plexpipe/plex-pipe/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23425779.svg)](https://doi.org/10.5281/zenodo.23425779)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/plexpipe/plex-pipe/main/docs/images/PlexPipe_logo_small_dark_transparent.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/plexpipe/plex-pipe/main/docs/images/PlexPipe_logo_small.png">
  <img alt="Logo" src="https://raw.githubusercontent.com/plexpipe/plex-pipe/main/docs/images/PlexPipe_logo_small.png">
</picture>


**PlexPipe turns raw multiplexed whole-slide images into quantitative single-cell data.** It takes the individual analysis-ready TIFF files and moves them through five modular steps, from outlining regions of interest to a single-cell feature table ready for downstream analysis in the [scverse](https://scverse.org/) ecosystem.

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

Install PlexPipe from PyPI, with every optional feature:

```bash
pip install "plex_pipe[all]"
```

or, with [uv](https://docs.astral.sh/uv/), `uv pip install "plex_pipe[all]"`. This gives you the `plex_pipe` library and the `plexpipe` command.

To run the notebooks, clone the repository and sync the full environment:

```bash
git clone https://github.com/plexpipe/plex-pipe.git
cd plex-pipe
uv sync --extra all
```

`--extra all` installs every optional feature: the segmentation backends (Cellpose, InstanSeg, PyTorch), the napari GUI, Jupyter, and Globus transfer. On a Windows machine with an NVIDIA GPU you need a CUDA build of PyTorch, covered in the [installation guide](https://plexpipe.github.io/plex-pipe/latest/usage/installation/).

**Supported platforms.** Python 3.12–3.14 on Linux, Windows and Apple Silicon Macs. Install `plex_pipe[all]`; PyTorch comes from PyPI and matches your platform (CUDA on Linux, CPU on Windows, CPU + Metal/MPS on macOS). On Windows with an NVIDIA GPU, install a CUDA build of PyTorch yourself, or use `uv sync --extra all-cuda` in a clone (see the [installation guide](https://plexpipe.github.io/plex-pipe/latest/usage/installation/)). Intel Macs are not supported: current PyTorch releases no longer include Intel-Mac builds.

## Try it on example data

After `pip install "plex_pipe[all]"`, this script runs the pipeline on a small example dataset: two tissue cores imaged with DAPI and three markers. `setup_example()` downloads the images (about 116 MB, once), writes a ready-to-use config and two small ROIs, so the interactive steps (ROI definition and quality control in napari) are skipped:

```python
import plex_pipe
from plex_pipe.io.filesystem import list_roi_stores
from plex_pipe.runners import (
    build_quant_controllers,
    build_resource_controllers,
    prepare_rois,
    quantify_roi,
    segment_roi,
)

# example images, a ready config and two small ROIs, in ./plexpipe_example
config = plex_pipe.load_config(plex_pipe.setup_example("plexpipe_example"))

# step 2: cut each ROI out of the images into its own SpatialData store
prepare_rois(config, plex_pipe.LocalFileStrategy(config)).run()

# steps 4 and 5: segment cells and nuclei, then measure them, ROI by ROI
segmenters = build_resource_controllers(config)
quantifiers = build_quant_controllers(config)
for roi in list_roi_stores(config.roi_dir_output_path):
    segment_roi(config, roi, segmenters)
    quantify_roi(roi, quantifiers)
```

It takes about a minute on a laptop CPU. Each ROI ends up as a SpatialData store in `plexpipe_example/output/example/rois/`, with the cell and nucleus masks and the per-cell table `instanseg_table`; open it with `spatialdata.read_zarr()` or in napari with [napari-spatialdata](https://github.com/scverse/napari-spatialdata). The config, `plexpipe_example/config.yaml`, is the starting point for your own data.

The notebooks walk through the same example step by step, including the interactive steps; they come with a clone of the repository, and the first notebook downloads the data with `fetch_example()`.

Start with `01_roi_definition_demo.ipynb` and work through to `05`. Stages 1 and 3 open a napari window for the interactive steps; the rest run automatically from the shared configuration file.

## Execution modes

For smaller datasets and prototyping, run the notebooks or standalone scripts locally. For large-scale parallel processing on HPC, use the Nextflow version, [plex-pipe-nextflow](https://github.com/plexpipe/plex-pipe-nextflow).

## Status

PlexPipe is in active development (alpha). Interfaces and the configuration schema may still change before a 1.0 release. Bug reports and feedback are welcome on the [issue tracker](https://github.com/plexpipe/plex-pipe/issues).

Automatic ROI suggestion with SAM2 (Segment Anything Model 2) is optional and installed separately (Linux or WSL on Windows); ROIs can always be drawn by hand.

## Used in

- Yang Y, Bukkuri A, Poe D, McLaughlin J, Hao S, Brown DD, Kedziora KM, Stallaert W. Distinct p21 dynamics drive alternative routes to whole-genome duplication through a common CDK4/6-dependent polyploid G0 state. *bioRxiv* [Preprint]. 2026 Jan 15:2026.01.15.699545. doi: [10.64898/2026.01.15.699545](https://doi.org/10.64898/2026.01.15.699545). PMID: 41648389; PMCID: PMC12871375.

## Similar projects

PlexPipe is one of several open pipelines for turning multiplexed images into single-cell data:

- [MCMICRO](https://mcmicro.org/)
- [Harpy](https://github.com/saeyslab/harpy)
- [Sopa](https://prism-oncology.github.io/sopa/)
- [Spatialproteomics](https://github.com/sagar87/spatialproteomics)


PlexPipe's distinguishing emphasis is human-in-the-loop interaction. Two of its five steps, ROI definition and quality control, open a napari viewer so a scientist can outline regions of interest and annotate imaging artefacts directly, keeping expert judgement at the points in the workflow where it matters most.

## License

Distributed under the terms of the BSD-3-Clause license.
