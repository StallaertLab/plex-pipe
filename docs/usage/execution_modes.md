# Usage

PlexPipe supports command-line execution and interactive analysis via Jupyter notebooks. For scalable workflows, it can also be orchestrated through Nextflow (see [plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow)).

Interactive [steps](../analysis_steps/00_steps_overview.md) (1 - Core detection and 3 - Quality Control) are designed to be executed using [Napari](https://napari.org/) with designed widgets.

---

## Choosing how to run

| Way to run | Use it for | Runs |
|---|---|---|
| **Notebooks** | Inspecting, prototyping, learning | Whatever you call, step by step |
| **Scripts** (`02_cut_rois.py`, `04_segment.py`, `05_quantify.py`) | Whole analyses on one machine | All channels / all ROIs in one process |
| **`plexpipe` command** ([Command Line](cli.md)) | Workflow managers such as Nextflow; re-running a single ROI | One channel image or one ROI per call |

All three use the same code, organised in three layers:

1. **Classes** in `plex_pipe.stages` (for example `CoreCutter`, `CoreAssembler`, `ResourceBuildingController`, `QuantificationController`) do the work. They take explicit arguments and do not read the config file. Notebooks can use them directly.
2. **`plex_pipe.runners`** reads the config and builds and runs these classes for one unit of work (for example `cut_image`, `assemble_roi`, `segment_roi`, `quantify_roi`). Notebooks can call these functions too.
3. **Orchestration** decides how many units run and when: the scripts loop over all channels and ROIs, `plexpipe` runs one unit per call, and Nextflow starts many `plexpipe` calls in parallel.

Because the scripts and `plexpipe` call the same functions in `plex_pipe.runners`, they give the same results.

---

## Command-Line Usage

To run the pipeline from the command line, use the provided scripts:

### Prepare Cores

```bash
python scripts/02_cut_rois.py --exp_config ../examples/example_pipeline_config.yaml
```

Add `--roi_cleanup` to delete the per-ROI TIFFs once each ROI is assembled.

or alternatively with [remote sourcing](./input_data.md#sourcing-image-files) of the image files:

```bash
python scripts/02_cut_rois.py --exp_config '../examples/example_pipeline_config_globus.yaml' --globus_config '../examples/example_globus_config.yaml' --from_collection 'remote_source' --to_collection 'local_workstation' --cleanup
```

`--cleanup` deletes each transferred image once its ROIs are cut.

### Image Processing
```bash
python 04_segment.py --exp_config ../examples/example_pipeline_config.yaml --overwrite
```

### Quantification
```bash
python 05_quantify.py --exp_config ../examples/example_pipeline_config.yaml --overwrite
```

---

## Jupyter Notebook Usage

For interactive inspection, prototyping, or educational purposes, the following notebooks illustrate how to use the components directly:

* **`core_selection_demo.ipynb`**: An interactive notebook that enables users to define cores as rectangles or polygons using the Napari viewer. It supports automatic core detection via [Segment Anything v2](https://github.com/facebookresearch/sam2), with the option to manually correct the detected shapes or draw new ones from scratch. This step is interactive and only available as a notebook. The result is a `core_info.csv` file containing core metadata for use in subsequent steps via either Jupyter or CLI.
* **`core_cutting_demo.ipynb`**: Demonstrates how to load a single image and metadata entry and apply the core cutting logic.
