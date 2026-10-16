# Usage

PlexPipe supports command-line execution and interactive analysis via Jupyter notebooks. For scalable workflows, it can also be orchestrated through Nextflow (see [plex-pipe-nextflow](https://github.com/plexpipe/plex-pipe-nextflow)).

The interactive [steps](../analysis_steps/00_steps_overview.md) (1 - ROI Definition and 3 - Quality Control) run in [napari](https://napari.org/) with PlexPipe's widgets, from the notebooks or from the scripts `01_define_rois.py` and `03_qc.py`.

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

To run the pipeline from the command line, use the scripts in `scripts/`. Run them from that folder, so that the relative paths in the example config (`../examples/...`) resolve:

```bash
cd scripts
```

### ROI Definition (interactive)

```bash
python 01_define_rois.py --exp_config ../examples/example_pipeline_config.yaml
```

Opens napari with the ROI widget. Draw or edit the ROIs, click **Save ROIs**, then close the window to finish.

### ROI Cutting

```bash
python 02_cut_rois.py --exp_config ../examples/example_pipeline_config.yaml
```

Add `--roi_cleanup` to delete the per-ROI TIFFs once each ROI is assembled.

or alternatively with [remote sourcing](./input_data.md#sourcing-image-files) of the image files:

```bash
python 02_cut_rois.py --exp_config '../examples/example_pipeline_config_globus.yaml' --globus_config '../examples/example_globus_config.yaml' --from_collection 'remote_source' --to_collection 'local_workstation' --cleanup
```

`--cleanup` deletes each transferred image once its ROIs are cut.

### Quality Control (interactive)

```bash
python 03_qc.py --exp_config ../examples/example_pipeline_config.yaml
```

Opens one napari window per ROI with the QC widget. Draw exclusion shapes, click **Save All**, then close the window to move to the next ROI. Add `--roi ROI_001` to review a single ROI.

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

For interactive inspection, prototyping, or learning, the notebooks in `notebooks/` walk through the five steps on the example data:

* **`01_roi_definition_demo.ipynb`**: define the ROIs (for example the cores of a tissue microarray) as rectangles or polygons in the napari viewer. This step is interactive and only available as a notebook. It saves the ROI table (`rois.pkl` / `rois.csv`) used by all later steps. Optional automatic ROI suggestion with [SAM2](https://github.com/facebookresearch/sam2) is in `extras/01_roi_definition_demo_sam.ipynb`.
* **`02_roi_cutting_demo.ipynb`**: preview the channel selection and cut every ROI into its own SpatialData store.
* **`03_QC_demo.ipynb`**: mark imaging artefacts in napari, per marker, for exclusion from analysis.
* **`04_segmentation_demo.ipynb`**: image enhancement, segmentation and mask building.
* **`05_quantification_demo.ipynb`**: per-cell measurements into an AnnData table.

`notebooks/extras/` has further examples: Globus transfers, Cellpose and InstanSeg on their own, the SpatialData viewer, and QC after quantification.
