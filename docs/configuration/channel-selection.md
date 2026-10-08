# 🎯 Channels: Manifest and Selection

Deciding which images enter the analysis happens in two stages:

1. **Channel manifest — what exists.** A list of every input file with its marker and round. It comes either from the file names (a naming preset) or from a CSV you provide.
2. **Selection rules — what is used.** Settings such as `include_channels`, `exclude_channels`, `use_markers`, `ignore_markers` and `earliest_round_markers` choose one channel per marker from the manifest.

All of these settings live in the `channels:` section of the config YAML file.

Both happen at the [ROI cutting step](../analysis_steps/02_roi_cutting.md). Channels left out there never reach the SpatialData objects, so [preview the selection](#previewing-the-channels) before cutting.

## Terminology

*   **Marker name**: the biological target being imaged (e.g. `DAPI`, `CD44`, `pRB`). It becomes the image layer name in each ROI's SpatialData object, and it is what you refer to in `additional_elements` (e.g. `input: [DAPI, CD44]`).
*   **Round**: the imaging round (cycle) in which the file was acquired.
*   **Channel name**: one acquisition, written as `{round:03d}_{marker}` (e.g. `001_DAPI`, `002_CD44`). It distinguishes the same marker imaged in different rounds.
*   **Channel manifest**: the list of all input files with their marker, round, and an optional `use` flag.

---

## Channel manifest

PlexPipe needs a manifest: for every file in `image_dir`, its marker and round. How you provide it depends on your data. Choose your path:

* **[Path A: Cell DIVE data](#path-a-cell-dive-data)**: files with their original Cell DIVE names. Nothing to prepare.
* **[Path B: Any other data (manifest CSV)](#path-b-any-other-data-manifest-csv)**: you provide a CSV listing every file with its marker and round.

All settings below go in your **config YAML file**, which is the single source of truth for an analysis. After changing the YAML, load the config again (`config = plex_pipe.load_config("your_config.yaml")`) before running anything.

### Path A: Cell DIVE data

This is the default. In the config YAML file you can leave it implicit or state it:

```yaml
channels:
  file_naming: celldive        # default; may be left out
```

Marker and round are parsed from the Cell DIVE file names:

Format: `[Prefix]_[Round].0.4_R000_[Dye]_[Marker]-[Suffix]_[...].ome.tif`

* **Round**: the number before `.0.4` (e.g. `1` from `..._1.0.4_...`, giving channel `001_...`).
* **Marker**:
    * If the `[Dye]` segment contains `DAPI` (any case), the marker is `DAPI`.
    * Otherwise, the marker is the segment after the dye with its **last** `-suffix` removed
      (`pH2AX-AF555` → `pH2AX`, `Ki-67-AF488` → `Ki-67`).
* The `_[...]` part after the marker is optional (`..._Cy3_CK7-01.ome.tif` → `CK7`).

| File | Round | Marker | Channel |
|---|---|---|---|
| `BLCA-1_1.0.4_R000_Cy3_pH2AX-AF555_FINAL_AFR_F.ome.tif` | 1 | `pH2AX` | `001_pH2AX` |
| `BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif` | 1 | `DAPI` | `001_DAPI` |

Check the result with [`preview_channels`](#previewing-the-channels) before cutting.

!!! tip "Any issues? Switch to Path B"
    If files are not recognised, marker names come out wrong, two files resolve to the same channel, or you want to rename markers, switch to [Path B](#path-b-any-other-data-manifest-csv).
    In the `channels:` section of the YAML file, replace `file_naming` with `manifest: /path/to/channels.csv`, reload the config and run `plex_pipe.save_manifest(config)`. It reads markers and rounds from your Cell DIVE file names into the new CSV, so you only edit what needs fixing.

### Path B: Any other data (manifest CSV)

You provide a CSV listing every file in `image_dir` with its marker and round.

#### CSV format

```text
file,marker,round,use
slide1_cycle1_Hoechst.tif,Hoechst,1,
slide1_cycle2_CD45.tif,CD45,2,
slide1_cycle3_CD45.tif,CD45,3,no
slide1_cycle3_CD8.tif,CD8,3,
```

| Column | Required | Meaning |
|---|---|---|
| `file` | yes | File name in `image_dir` (no folders). Must match an existing file exactly. |
| `marker` | yes | Marker name used throughout the pipeline. |
| `round` | no | Imaging round, a whole number ≥ 0. Blank or missing column → `1`. |
| `use` | no | Blank or missing column → the file may be used. `no` removes the file **before** the selection rules run. |

* Accepted `use` values (any case): `yes`, `y`, `true`, `t`, `1` and `no`, `n`, `false`, `f`, `0`. Anything else is an error that names the row.
* Comma, semicolon or tab separators are all accepted, so the CSV can be saved by any editor or spreadsheet program, in any locale.
* Extra columns (e.g. `notes`) are ignored.
* Every file listed must exist in `image_dir`. Otherwise, the run stops and names the missing files. When files are sourced through Globus, no transfer is started.
* Files in `image_dir` that are not in the CSV are ignored and listed in the log.
* Rows with an empty marker, and two rows with the same marker and round, are rejected with the row numbers named, so an unfinished CSV cannot be used by accident.

#### Marker names matter

* **One channel is kept per marker.** To keep two rounds of the same marker, give them different marker names, e.g. `CD45` and `CD45_1`. The rules then treat them as separate markers.
* **Use the real name of your nuclear stain.** By default the earliest round is kept for `DAPI` and the latest round for every other marker. For a stain such as Hoechst, keep the name `Hoechst` and add it to [`earliest_round_markers`](#2-default-round-selection) in the config YAML file.

#### Creating the CSV

**1. Point the config YAML file at the CSV.** The CSV does not need to exist yet. Remove `file_naming` if it is there (setting both is an error).

```yaml
channels:
  manifest: /path/to/channels.csv
```

**2. Create the CSV.**

```python
import plex_pipe

config = plex_pipe.load_config("your_config.yaml")
plex_pipe.save_manifest(config)
```

This writes the CSV at the `manifest` path, with one row per file in `image_dir`. For files with Cell DIVE names, `marker` and `round` are read from the name; all other rows have an empty `marker` and `round` for you to fill in. An existing file is never overwritten unless you pass `overwrite=True`.

**3. Fill in the CSV** in any program that opens CSV files (a text editor or a spreadsheet program), following the [format above](#csv-format). Set `use` to `no`, or delete the row, for files you never want.

**4. Check the selection** with [`preview_channels(config)`](#previewing-the-channels). The CSV is read each time, so you don't need to reload the config after editing it.

**5. Cut.** Until the CSV exists and every row has a marker, the ROI cutting step stops with a message saying what is missing.

!!! note "Paths"
    A relative `manifest` path (like `image_dir`) is resolved against the folder you **run from**.
    A path that works from `notebooks/` will not work for a script started from the repository root.
    For scripts and Slurm jobs, use absolute paths.

    If `manifest` is not set, `save_manifest(config)` writes to `channels.csv` in the analysis directory; you can also pass any path: `save_manifest(config, "my_channels.csv")`.

### Previewing the channels

```python
table = plex_pipe.preview_channels(config)
```

`preview_channels` shows which files will be used, and why, before anything is cut. **Nothing is saved**: the result is a table (a pandas DataFrame) held in the variable, which you can print or display in a notebook. It has one row per file: `file, marker, round, use, channel, selected, reason`.

It runs exactly the same rules as the real run, but never stops at the first problem: unrecognised files, duplicate channels, files missing from `image_dir`, files not in the CSV, or a CSV not created yet all appear as rows with a reason.

For the example dataset (with `ignore_markers: [bCat]` in the config):

| file | marker | round | channel | selected | reason |
|---|---|---|---|---|---|
| `sample_1.0.4_R000_Cy5_CD45-AF647_FINAL_AFR_F.tiff` | CD45 | 1 | `001_CD45` | True | selected |
| `sample_1.0.4_R000_DAPI__FINAL_F.tiff` | DAPI | 1 | `001_DAPI` | True | selected |
| `sample_1.0.4_R000_Cy7_NaKATPase-AF750_FINAL_AFR_F.tiff` | NaKATPase | 1 | `001_NaKATPase` | True | selected |
| `sample_1.0.4_R000_Cy3_bCat-AF555_FINAL_AFR_F.tiff` | bCat | 1 | `001_bCat` | False | ignore_markers |

Both `preview_channels` and `save_manifest` also work for Globus data: pass `gc=...` (see [Globus Configuration](../usage/globus.md#configuration-registry)).

---

## Selection rules

The pipeline supports fine-grained control over which channels are processed. This is needed because:

- The same marker may be imaged in several rounds (e.g. re-staining or optimization).
- DAPI is typically acquired in every round for registration, but usually only one version is kept for analysis.

**One channel is kept per marker.** The rules below decide which one.

### Order of operations

The rules are applied **on top of the manifest**, in this order:

1. **Manifest `use` column**: files with `use` = `no` are removed first.
2. **Per marker, choose one channel:**
    1. `include_channels`: if any channel of this marker is listed, it is used; round selection is skipped.
    2. `exclude_channels`: listed channels are removed.
    3. **Default round selection**: the **latest round** is kept; for markers in `earliest_round_markers` (default: `DAPI`), the **earliest round**.
3. **Filter whole markers:** `use_markers`, then `ignore_markers`.

### 1. **Manifest `use` column**
- Optional column in a [manifest CSV](#csv-format); blank means the file may be used.
- `no` removes that file before any rule runs. Round selection then works with what is left: excluding round 3 of CD45 makes round 2 the latest.
- Not available on Path A (Cell DIVE names); there, exclude a single file with `exclude_channels` (e.g. `002_CD45`), since each file is one channel.

### 2. **Default round selection**
- For each marker imaged in several rounds, the **latest round** is used.
- For markers listed in `earliest_round_markers`, the **earliest available round** is used instead (`001_DAPI` for Cell DIVE data). Marker names are matched regardless of case.
- This is typically the marker used to align the rounds (e.g. DAPI); its first round usually has the best quality.
- The default is `earliest_round_markers: ["DAPI"]`. Change it in the config YAML file, for example for a different nuclear stain:

```yaml
channels:
  earliest_round_markers: ["Hoechst"]
```

- Set it to `[]` to keep the latest round for every marker.

### 3. **Using `include_channels`**
- A list of channel names like `002_CD44`, `001_DAPI`.
- If a marker has a listed channel, that channel is used; this **overrides automatic selection** for that marker.
- Use it to **force an earlier round**.
- Listing several channels of the same marker is an error (one channel per marker). To keep two rounds, give them different marker names in a [manifest CSV](#marker-names-matter).

### 4. **Using `exclude_channels`**
- A list of channel names to skip.
- For markers without an `include_channels` entry, the listed channels are removed before round selection.
- Example: excluding `003_pRB` falls back to `002_pRB` (or drops pRB if it has no other round).

### 5. **Using `use_markers`**
- A list of **marker names** (like `DAPI`, `pRB`, `CD44`), without the round prefix.
- Applied after channel selection: only these markers are kept.

### 6. **Using `ignore_markers`**
- A list of **marker names** to drop from the final set.
- Applied after `use_markers`.
- Use it to **discard a marker entirely** (e.g. if it failed quality control in every round).

### Examples

All examples below go in the `channels:` section.

#### Example 1: Default automatic selection
```yaml
channels:
  include_channels: []
  exclude_channels: []
  use_markers: []
  ignore_markers: []
  earliest_round_markers: ["DAPI"]
```

* Keeps the **latest round per marker**, and the **earliest DAPI round**.

#### Example 2: Force an earlier pRB round

```yaml
include_channels: ["001_pRB"]
```

* `001_pRB` is used even if `003_pRB` exists.

#### Example 3: Exclude a problematic round

```yaml
exclude_channels: ["003_CD44"]
```

* The latest remaining round of CD44 is used (e.g. `002_CD44`).

#### Example 4: Only process DAPI and CD44

```yaml
use_markers: ["DAPI", "CD44"]
```

* The final set contains only these two markers.

#### Example 5: Exclude a file in the manifest

```text
file,marker,round,use
slide1_cycle2_CD45.tif,CD45,2,
slide1_cycle3_CD45.tif,CD45,3,no
```

* Round 3 is removed by the manifest; the default rule then keeps round 2 (`002_CD45`).

#### Example 6: Keep two rounds of the same marker

```text
file,marker,round,use
slide1_cycle2_CD45.tif,CD45_1,2,
slide1_cycle3_CD45.tif,CD45,3,
```

* `CD45_1` and `CD45` are different markers, so both are kept as separate image layers.

#### Example 7: Hoechst as the nuclear stain

```yaml
earliest_round_markers: ["Hoechst"]
```

* The earliest Hoechst round is kept, and the image layer is named `Hoechst`.

### Conflicting settings

Settings that ask for and reject the same thing are an error. The config does not load, so nothing runs:

* several channels of the same marker in `include_channels`;
* the same channel in `include_channels` and `exclude_channels`;
* a channel in `include_channels` whose marker is in `ignore_markers`, or missing from `use_markers` when `use_markers` is set;
* the same marker in `use_markers` and `ignore_markers`.

A channel in `include_channels` whose file has `use` = `no` in the manifest is also an error, raised when the channels are selected. `preview_channels` shows it in that file's reason instead.

A marker in `use_markers` or `ignore_markers` that is not found only produces a warning.

---

## Checking what was used

* **Before running:** `plex_pipe.preview_channels(config)` gives every file a `reason` (e.g. `superseded by 003_CD3`, `exclude_channels`, `ignore_markers`, `excluded in manifest (use=no)`). See [Previewing the channels](#previewing-the-channels).
* **After running:** the ROI cutting log (in the analysis `logs/` folder when run through `scripts/02_cut_rois.py`) records the channel source (`Channel source: naming preset 'celldive'` or `Channel source: manifest <path>`), the final selected channels, every unused file with its reason, and files that were not recognised or not listed in the manifest.
