# 🔧 Configuration

The configuration file serves as the central blueprint for the PlexPipe analysis.
It provides parameters for all stages of the pipeline divided into sections corresponding to the [analysis steps](../what_is_plexpipe.md).

---
### Config Validation

To ensure your configuration is valid, the system validates your input against a predefined schema.

Validation Rules:

*   **Required Fields**: These must be present in your configuration file. If a required field is missing, the application will return an error.

*   **Optional Fields**: These are labeled as (optional). You can choose to:

    * Omit them entirely (the system will use its default behavior).
    * Set them to null (or ~) to explicitly signify no custom value.
    * Provide a custom value to override the default.

---

### Path Format

When entering file paths in this configuration file, always use the forward slash (/) as the folder separator, even on Windows.
The backslash (\\) is a "special character" in YAML. Using it can cause errors or require you to "double-up" your slashes (e.g., C:\\\Users).

Correct: C:/path/to/images Avoid: C:\path\to\images.

---

## Examples

Full example configuration files can be found in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples).

---

## General Settings

Global paths and analysis naming.

```yaml
# -----------------------------------------------------------------------------
# 1. General Settings
# -----------------------------------------------------------------------------
general:
  image_dir: C:/path/to/images
  analysis_name: experiment_01
  analysis_root_dir: C:/analysis_out
  log_dir: null
```

| Key                        | Type        | Description                                        |
| -------------------------- | ----------- | ---------------------------------------------------|
| `image_dir`                | `Path`       | Source directory with tiff images. For differences between the local and Globus use see [Input Data](../usage/input_data.md). |            |
| `analysis_name`            | `str`       | Name of the analysis run.                          |
| `analysis_root_dir`        | `Path`       | Analysis output base directory. Analysis will be saved in `analysis_toot_dir/analysis_name` referred to as `analysis_dir`.|
| `log_dir`                  | `Path` (optional)       | Custom log directory. Defaults to `analysis_dir/logs`.   |

## Core Detection

```yaml
######################################################
# core detection
######################################################
core_detection:
  detection_image: "BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif"
  core_info_file_path: null

  sam:
    im_level: 6
    min_area: 2000
    max_area: 20000
    min_iou: 0.8
    min_st: 0.9
    min_int: 15
    frame: 4
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `detection_image` | `str` | **Required.** Name of the image in `image_dir` used for defining cores. |
| `core_info_file_path` | `Path (optional)` | Custom path for core coordinates. Defaults to `analysis_dir/cores.csv`. |
| **sam** | **Group (optional)** | **SAM2 Configuration.** If this key is present, all sub-fields below must be specified. |
| `sam.im_level` | `int` | Pyramid level to read from the image for core definition. |
| `sam.min_area` | `int` | Minimum pixel area for a detected core to be considered valid. |
| `sam.max_area` | `int` | Maximum pixel area for a detected core to be considered valid. |
| `sam.min_iou` | `float` | SAM2 intersection-over-union threshold for mask quality. |
| `sam.min_st` | `float` | SAM2 stability score threshold. |
| `sam.min_int` | `int` | SAM2 intensity threshold for mask filtering. |
| `sam.frame` | `int` | Number of pixels to add as padding to the core bounding box. |

For detailed examples of how to configure SAM2 using various parameter settings, please refer to the official [SAM2 repository](https://github.com/facebookresearch/sam2).

## Core Cutting

```yaml
######################################################
# core cutting
######################################################
core_cutting:
  cores_dir_tif: null # => ${analysis_dir}/cores
  cores_dir_output: null # => ${analysis_dir}/temp

  include_channels:
  exclude_channels:
    - 008_ECad
  use_markers:
  ignore_markers:
    - Antibody1
  margin: 0
  mask_value: 0
  transfer_cleanup_enabled: True
  core_cleanup_enabled: True
```

| Key                        | Type        | Description                                                             |
| -------------------------- | ----------- | ----------------------------------------------------------------------- |
| `cores_dir_tif`            | `Path` (optional)       | Temporary folder to store extracted TIFFs for each core. Defaults to `analysis_dir/temp`. |
| `cores_dir_output`         | `Path` (optional)       | Final destination for SpatialData (Zarr) outputs. Defaults to `analysis_dir/cores`.       |
| `include_channels`         | `list[str]` (optional)  | List of channel names to include.           |
| `exclude_channels`         | `list[str]` (optional)  | List of channel names to exclude.                             |
| `use_markers`              | `list[str]` (optional)  | List to restrict markers to analyze. |
| `ignore_markers`           | `list[str]` (optional)  | List to ignore markers.|
| `margin`                   | `int` (optional) | Number of pixels to pad around each bounding box when cutting cores. Defaults to 0.    |
| `mask_value`               | `int` (optional) | Value used to fill background for polygonal core masks. Defaults to 0.                 |
| `transfer_cleanup_enabled` | `bool` (optional) | Whether to delete temporary files downloaded via Globus after the run. Defaults to False.|
| `core_cleanup_enabled`     | `bool` (optional) | Whether to delete TIFFs from `cores_dir_tif` after core assembly. Defaults to False. For details see [Input Data](../usage/input_data.md).|

Parameters `include_channels`, `exclude_channels`, `use_markers` and `ignore_markers` provide a fine-grained control over which imaging channels are included in processing. See [Channel Selection Logic](channel-selection.md) for details.



## Image Processing

```yaml
# -----------------------------------------------------------------------------
# 4. Image Processing (Filtering, Segmentation, Buiding Derivative Masks etc.)
# -----------------------------------------------------------------------------
additional_elements:

  - category: image_filter
    type: normalize
    input: [DAPI, HLA1]
    output: "${input}_norm"
    parameters:
      low: 1
      high: 99.8
    keep: false

  - category: object_segmenter
    type: instanseg
    parameters:
      model: fluorescence_nuclei_and_cells
      pixel_size: 0.3
      resolve_cell_and_nucleus: true
      cleanup_fragments: true
      clean_cache: true
      normalise: false
    input:
      - DAPI_norm
      - HLA1_norm
    output:
      - instanseg_nucleus
      - instanseg_cell
    keep: true

  - category: mask_builder
    type: ring
    input:
        - instanseg_nucleus
    output: ring
    parameters:
      outer: 8
      inner: 2
    keep: true
```

The pipeline allows for flexible image processing steps defined in the [Processors](..) list. Each entry in this list is a processing unit that takes inputs (images or labels), performs an operation, and produces outputs.

### Structure of an Element

| Key | Type | Description |
| :--- | :--- | :--- |
| `category` | `str` | The category of the operation. Options: `image_filter`, `object_segmenter`, `mask_builder`. |
| `type` | `str` | The specific operation name (e.g., `normalize`, `instanseg`). |
| `input` | `str` \| `list` | The name(s) of input images or channels. |
| `output` | `str` \| `list` | The name(s) assigned to the results. Supports variable expansion like `${input}_norm`. |
| `parameters` | `dict` (optional) | Specific parameters for the operation. |
| `keep` | `bool` (optional) | Whether to save the output to the final Zarr file (`true`) or keep it temporary (`false`). Defaults to `false`. |

For a complete list of available operations and their parameters, see [Processors](../usage/processors.md).

## Quality Control

## Quantification

```yaml


```

## Storage Settings

```yaml
sdata_storage:
  chunk_size: [1, 512, 512]
  max_pyramid_level: 3
  downscale: 2
```

| Key | Type | Description |
| :--- | :--- | :--- |
| chunk_size | list[int] (optional) | Dimensions of the data chunks stored in the Zarr array Defaults to [1, 512, 512].|
| max_pyramid_level | int (optional) | Number of multiscale pyramid levels to generate. Defaults to 4.|
| downscale | int (optional) | Downsampling factor applied between consecutive pyramid levels. Defaults to 2.|
