# Command Line (`plexpipe`)

`plexpipe` runs PlexPipe **one unit of work at a time**: one channel image, or one ROI. It is meant for workflow managers such as [Nextflow](https://www.nextflow.io/) ([plex-pipe-nextflow](https://github.com/StallaertLab/plex-pipe-nextflow)), which start one job per unit and run many of them in parallel. It is also handy for re-running a single ROI by hand.

To run a whole analysis in one go, use the scripts `02_cut_rois.py`, `04_segment.py` and `05_quantify.py` instead (see [Execution Modes](execution_modes.md)). Both call the same functions in `plex_pipe.runners`, so they give the same results.

---

## Installation

`plexpipe` is installed together with the package; it is registered in `pyproject.toml` under `[project.scripts]`. After installing (or, for an existing editable install, after re-running `pip install -e .` / `uv pip install -e .` once), check:

```bash
plexpipe --help
```

The same commands are also available as `python -m plex_pipe <command> ...`.

---

## Before you start: absolute paths

Each `plexpipe` call may run in a different folder (Nextflow gives every job its own working directory), so **all paths in the config YAML file must be absolute**: `general.image_dir`, `general.analysis_dir`, and, if set, `general.log_dir`, `channels.manifest`, `roi_definition.roi_info_file_path`, `roi_cutting.roi_dir_tif` and `roi_cutting.roi_dir_output`. Every command stops with an error that lists any relative path.

The ROIs must already be defined (the ROI table at `roi_info_file_path`, see [ROI Definition](../analysis_steps/01_roi_definition.md)).

---

## The order of the commands

| Step | Command | Runs once per |
|---|---|---|
| 1 | `plexpipe setup` | analysis |
| 2 | `plexpipe cut-image` | channel (row of `images.csv`) |
| 3 | `plexpipe assemble-roi` | ROI (row of `rois.csv`), after **all** channels are cut |
| 4 | `plexpipe segment-roi` | ROI |
| 5 | `plexpipe quantify-roi` | ROI |

Step 3 must wait until step 2 has finished for every channel, because each ROI is assembled from all of its channels. Steps 3–5 can run in parallel for different ROIs.

The same sequence as a plain shell script (one job after the other, without Nextflow):

```bash
C=/abs/path/to/config.yaml
J=/abs/path/to/work        # where setup writes images.csv and rois.csv

plexpipe setup --exp_config "$C" --out_dir "$J"

tail -n +2 "$J/images.csv" | while IFS=, read -r ch path task; do
  plexpipe cut-image --exp_config "$C" --channel "$ch" --image_path "$path"
done

tail -n +2 "$J/rois.csv" | while IFS=, read -r roi path; do
  plexpipe assemble-roi --exp_config "$C" --roi "$roi" --images "$J/images.csv"
  plexpipe segment-roi  --exp_config "$C" --roi_path "$path"
  plexpipe quantify-roi --exp_config "$C" --roi_path "$path"
done
```

---

## The files written by `setup`

`setup` writes two CSV files (Unix line endings) into `--out_dir`. The other commands, or the workflow manager, read them.

**`images.csv`**: one row per selected channel.

| Column | Meaning |
|---|---|
| `channel` | Channel name, as selected by the `channels:` section of the config. |
| `path` | Local path of the channel image (for Globus runs: where the transferred copy will appear). |
| `task_id` | Globus transfer task to wait for before cutting; empty for local images and for images already present. |

**`rois.csv`**: one row per ROI in the ROI table.

| Column | Meaning |
|---|---|
| `roi_name` | ROI name. |
| `path` | The ROI's SpatialData store (`<roi_dir_output>/<roi_name>.zarr`). |

---

## Commands

All commands take `--exp_config` (path to the config YAML file).

### `plexpipe setup`

Finds the selected channels (warning if later steps need markers that will not be cut), starts the Globus transfers if requested, and writes `images.csv` and `rois.csv`.

| Option | Meaning |
|---|---|
| `--out_dir` | Folder for `images.csv` and `rois.csv` (default: current folder). |
| `--globus_config` | Globus config YAML; fetch the images from a remote collection (see [Globus Setup](globus.md)). One transfer task per channel. |
| `--from_collection` | Key of the source collection in the Globus config (default `remote_source`). |
| `--to_collection` | Key of the destination collection, this machine (default `local_workstation`). |
| `--file_checksum` | Transfer images that are already present too (Globus compares checksums). By default they are skipped. |

### `plexpipe cut-image`

Cuts every ROI from one channel image and saves one TIFF per ROI in `roi_dir_tif`. Uses `roi_cutting.margin` and `mask_value` from the config.

| Option | Meaning |
|---|---|
| `--channel` | Channel name (from `images.csv`). |
| `--image_path` | Path to the image (from `images.csv`). |
| `--task_id` | Globus task to wait for before cutting (from `images.csv`); needs `--globus_config`. |
| `--globus_config`, `--from_collection`, `--to_collection` | As for `setup`; only needed with `--task_id`. |
| `--wait_hours` | How long to wait for the Globus task (default 12). |
| `--poll_seconds` | Seconds between Globus status checks (default 30). |
| `--cleanup`, `-c` | Delete the transferred image once it is cut. Only images transferred into the analysis `temp` folder are deleted, never the originals. |

### `plexpipe assemble-roi`

Assembles one ROI's channel TIFFs into its SpatialData store. Every channel listed in `images.csv` must have been cut for this ROI; otherwise the command stops and names the missing channels. This keeps all ROIs of an analysis with the same channels, so their quantification tables are comparable.

| Option | Meaning |
|---|---|
| `--roi` | ROI name (from `rois.csv`). |
| `--images` | Path to `images.csv`. |
| `--roi_cleanup` | Delete this ROI's TIFFs once it is assembled. |

### `plexpipe segment-roi`

Runs the `additional_elements` steps of the config (image enhancement, segmentation, mask building) on one ROI, after checking that every step's inputs exist.

| Option | Meaning |
|---|---|
| `--roi_path` | Path to the ROI's `.zarr` store (from `rois.csv`). |
| `--overwrite` | Overwrite elements that already exist. |

### `plexpipe quantify-roi`

Runs the `quant` tables of the config on one ROI.

| Option | Meaning |
|---|---|
| `--roi_path` | Path to the ROI's `.zarr` store (from `rois.csv`). |
| `--overwrite` | Overwrite tables that already exist. |

---

## Run settings

Some options change how a run behaves but not what the results are: `--cleanup`, `--roi_cleanup`, `--overwrite`, `--file_checksum` and the Globus options. They are command-line options, not config settings, and each run writes the cleanup settings it used to its log, for example:

```
Run setting roi_cleanup: on (command line)
```

For existing configs, `transfer_cleanup_enabled` and `roi_cleanup_enabled` under `roi_cutting:` still turn cleanup on (the log then says `on (config)`).

!!! warning "Cleanup and retries"
    With `--cleanup`, a transferred image is deleted after it is cut. If that `cut-image` job is then run again (for example by an automatic retry), its input is gone. Do not retry `cut-image` jobs that use `--cleanup`.

---

## Logs and config snapshots

Every command writes its own log file to the analysis `logs` folder, named after the command and the unit, for example `cut-image_DAPI_2026-10-09_18-47-19.log` or `segment-roi_ROI_000_2026-10-09_18-47-24.log`. Every command also records which [config snapshot](../configuration/config_overview.md#config-snapshots) it used, like the scripts do.

---

## Re-running one ROI

To redo a single ROI, for example after changing a segmentation step in the config, run only the commands for that ROI:

```bash
plexpipe segment-roi  --exp_config /abs/path/to/config.yaml --roi_path /abs/path/to/analysis/rois/ROI_007.zarr --overwrite
plexpipe quantify-roi --exp_config /abs/path/to/config.yaml --roi_path /abs/path/to/analysis/rois/ROI_007.zarr --overwrite
```
