# Changelog

All notable changes to PlexPipe are listed here, starting with the first release. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Changes to the config file format are listed in the Schema Changelog (`docs/configuration/schema_changelog.md`).

## [Unreleased]

### Added

- `setup_example()` sets up a ready-to-run example (images, config with absolute paths, two small ROIs), so the example runs after `pip install`, without a clone; README quickstart.

## [0.1.0] - 2026-10-15

First public release.

### Added

- Five-step pipeline from multiplexed whole-slide images to single-cell data: ROI definition, ROI cutting, quality control, segmentation and quantification, driven by one YAML config file (`schema_version` 2.0).
- Interactive steps in napari: drawing and editing ROIs (`RoiWidget`), and marking artefacts to exclude from analysis (`QCWidget`).
- Channel discovery from image file names (naming preset, e.g. `celldive`) or from a channel manifest CSV (`save_manifest`, `preview_channels`).
- ROI cutting into one SpatialData (Zarr) store per ROI, from local files or through Globus transfers.
- Segmentation with Cellpose or InstanSeg, with image enhancers (`normalize`, `denoise_with_median`, `mean_of_images`) and mask builders (`ring`, `subtract`, `multiply`, `blob`).
- Quantification of per-cell morphology and marker intensities into AnnData tables, with QC exclusion columns.
- Three ways to run: the notebooks in `notebooks/`, the scripts `01`–`05` in `scripts/`, and the `plexpipe` command (`setup`, `cut-image`, `assemble-roi`, `segment-roi`, `quantify-roi`), which runs one image or ROI per call for HPC schedulers and Nextflow ([plex-pipe-nextflow](https://github.com/plexpipe/plex-pipe-nextflow)).
- Config checks: unknown or misspelled keys are an error, older configs are migrated, and each run saves a snapshot of its config with the PlexPipe version.
- `fetch_example()` downloads a small example dataset for the notebooks.
- Python 3.12–3.14 on Linux, Windows and Apple Silicon Macs.

[0.1.0]: https://github.com/plexpipe/plex-pipe/releases/tag/v0.1.0
