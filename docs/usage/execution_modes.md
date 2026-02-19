# Usage

PlexPipe supports command-line execution and interactive analysis via Jupyter notebooks. For scalable workflows, it can also be orchestrated through Nextflow (see [plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow)).

Interactive [steps](../analysis_steps/00_steps_overview.md) (1 - Core detection and 3 - Quality Control) are designed to be executed using [Napari](https://napari.org/) with designed widgets.

---

## Command-Line Usage

To run the pipeline from the command line, use the provided scripts:

### Prepare Cores

```bash
python scripts/02_cut_rois.py --exp-config ../examples/example_pipeline_config.yaml
```

or alternatively with [remote sourcing](./input_data.md#sourcing-image-files) of the image files:

```bash
python scripts/02_cut_rois.py --exp_config '../examples/example_pipeline_config_globus.yaml' -globus_config '../examples/example_globus_config.yaml' --from_collection 'r_collection_id' --to_collection 'cbi_collection_id'  --cleanup
```

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
