The following sections detail the configuration parameters for each step of the pipeline.

## Schema Version

```yaml
schema_version: "2.0"
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `schema_version` | `str` | Version of the config file format, `"MAJOR.MINOR"`, in quotes. The current version is `"2.0"`. Older configs are upgraded automatically when loaded; see [Schema Version and Migration](config_overview.md#schema-version-and-migration). |

## General Settings

This section defines the fundamental paths and naming conventions for the analysis run, including the source image directory and the output location.

```yaml
general:
  image_dir: C:/path/to/images
  analysis_name: experiment_01
  analysis_dir: C:/analysis_out
  log_dir: null
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `image_dir` | `Path` | Source directory with TIFF images. In local mode, `image_dir` should point to a folder on a local system. In Globus mode, `image_dir` should reflect the remote directory on the Globus endpoint. |
| `analysis_name` | `str` | Name of the analysis run. |
| `analysis_dir` | `Path` | Analysis output base directory. The analysis is saved in `analysis_dir/analysis_name`, referred to below as the analysis directory. |
| `log_dir` | `Path` (optional) | Custom log directory. Defaults to `logs` in the analysis directory. |

## Channels

This section defines where marker names and rounds come from (the channel manifest) and which channels are used. The whole section is optional; leaving it out uses the defaults.

```yaml
channels:
  file_naming: celldive
  # manifest: /path/to/channels.csv
  earliest_round_markers: [DAPI]
  include_channels: []
  exclude_channels: []
  use_markers: []
  ignore_markers: []
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `file_naming` | `str` (optional) | Naming preset used to read marker and round from file names. Available: `celldive`. Used when `manifest` is not set. |
| `manifest` | `Path` (optional) | Path to a channel manifest CSV listing every file with its marker and round. Set either `file_naming` or `manifest`, not both. |
| `earliest_round_markers` | `list[str]` (optional) | Markers for which the earliest round is kept instead of the latest. Defaults to `[DAPI]`. |
| `include_channels` | `list[str]` (optional) | Channel names (e.g. `002_CD44`) to use for their marker, bypassing round selection. |
| `exclude_channels` | `list[str]` (optional) | Channel names to skip. |
| `use_markers` | `list[str]` (optional) | If set, only these markers are used. |
| `ignore_markers` | `list[str]` (optional) | Markers to leave out. |

See [Channel Selection](channel-selection.md) for the manifest CSV format and how the selection rules work together.

## ROI Definition

This section specifies the image used to define the regions of interest (ROIs) and where their coordinates are stored.

```yaml
roi_definition:
  detection_image: "BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif"
  roi_info_file_path: null
  im_level: 6
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `detection_image` | `str` | **Required.** Name of the image in `image_dir` used for defining ROIs. |
| `roi_info_file_path` | `Path` (optional) | Custom path for ROI coordinates. Defaults to `rois.pkl` in the analysis directory. |
| `im_level` | `float` (optional) | Pyramid level to read from the image for ROI definition. If not specified, all pyramid levels are read from the input image. |

## ROI Cutting

This section controls the extraction of individual ROIs from the original whole-slide images: output directories, margins and masking. Which channels are cut is set in [Channels](#channels).

```yaml
roi_cutting:
  roi_dir_tif: null
  roi_dir_output: null
  margin: 0
  mask_value: 0
  transfer_cleanup_enabled: false
  roi_cleanup_enabled: false
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `roi_dir_tif` | `Path` (optional) | Temporary folder to store extracted TIFFs for each ROI. Defaults to `temp` in the analysis directory. |
| `roi_dir_output` | `Path` (optional) | Final destination for SpatialData (Zarr) outputs. Defaults to `rois` in the analysis directory. |
| `margin` | `int` (optional) | Number of pixels to pad around each bounding box when cutting ROIs. Defaults to 0. |
| `mask_value` | `int` (optional) | Value used to fill the background for polygonal ROI masks. Defaults to 0. |
| `transfer_cleanup_enabled` | `bool` (optional) | Whether to delete temporary files downloaded via Globus after the run. Defaults to false. |
| `roi_cleanup_enabled` | `bool` (optional) | Whether to delete TIFFs from `roi_dir_tif` after ROI assembly. Defaults to false. For details see [Input Data](../usage/input_data.md). |

## Quality Control

This section manages quality control parameters, specifically defining prefixes for exclusion masks.
These masks are used to filter out artifacts or unwanted regions from downstream analysis.

```yaml
qc:
  prefix: qc_exclude
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `prefix` | `str` | **Required.** Prefix for shapes used for quality control exclusion. Shapes named `{prefix}_{marker}` will be used to mask out objects for specific markers. |


## Image Processing

```yaml
additional_elements:

  - category: image_enhancer
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
      rad_bigger: 8
      rad_smaller: 2
    keep: true
```

The pipeline allows for flexible image processing steps defined in the [Processors](../usage/processors.md) list.
Each entry in this list is a processing unit that takes inputs (images or labels), performs an operation, and produces outputs.
Processing steps are executed sequentially, meaning the order of the list determines the flow of data, and the output of one step is typically required for the next.

### Structure of an Element

| Key | Type | Description |
| :--- | :--- | :--- |
| `category` | `str` | The category of the operation. Options: `image_enhancer`, `object_segmenter`, `mask_builder`. |
| `type` | `str` | The specific operation name (e.g., `normalize`, `instanseg`). |
| `input` | `str` \| `list` | The name(s) of input images or channels. |
| `output` | `str` \| `list` | The name(s) assigned to the results. Supports variable expansion like `${input}_norm`. |
| `parameters` | `dict` (optional) | Specific parameters for the operation. |
| `keep` | `bool` (optional) | Whether to save the output to the final Zarr file (`true`) or keep it temporary (`false`). Defaults to `false`. |

For a complete list of available operations and their parameters, see [Processors](../usage/processors.md).

## Quantification

The `quant` section allows you to define one or more quantification tasks.
Each entry in the list corresponds to a separate AnnData table that will be generated and stored in the SpatialData object.
This is useful if you have multiple segmentation results (e.g., cells and nuclei, or different cell segmentation models) and want to quantify them independently.
Example below specifies only a single AnnData table to be created ('instanseg_table').

```yaml
quant:
  - name: instanseg_table
    masks:
      nucleus: instanseg_nucleus
      cell: instanseg_cell
      ring: ring
      cyto: cytoplasm
    layer_connection: instanseg_cell
    morphological_properties:
      - label
      - centroid
      - area
    intensity_properties:
      - median
    markers_to_quantify:
      - DAPI
      - HLA1
    qc_to_table: True
```

| Key | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Name of the output AnnData table to be saved in the SpatialData object. |
| `masks` | `dict[str, str]` | Dictionary mapping suffixes (e.g., nucleus, cell) to the actual mask layer names in the SpatialData object. |
| `layer_connection` | `str` (optional) | The mask layer name to which the table should be linked (e.g. for visualization in Napari Spatialdata plugin). |
| `morphological_properties` | `list[str]` (optional) | List of morphological features to calculate. 'Label' is added automatically if absent from the custom list to identify objects. Defaults to ["label", "centroid", "area", "eccentricity", "solidity", "perimeter", "euler_number"].|
| `intensity_properties` | `list[str]` (optional) | List of intensity metrics to calculate. Defaults to ['mean', 'median']. |
| `markers_to_quantify` | `list[str]` (optional) | List of specific markers to quantify itensity properties. If omitted, all available channels are quantified. |
| `qc_to_table` | `bool` (optional) | If True, uses polygons defined in the QC step to create a mask layer in the AnnData table indicating which objects are from the accepted regions. Defaults to False. |

For `morphological_properties`, any property supported by skimage.measure.regionprops can be used.

For `intensity_properties`, currently implemented metrics include `mean`, `median` `min`, `max`, `std` and `sum`. If you require other metrics, please open an issue on [GitHub](https://github.com/StallaertLab/plex-pipe/issues).



## Storage Settings

This section defines the storage parameters for the resulting SpatialData objects (Zarr files). It controls performance-related settings such as chunk sizes and the generation of multi-scale image pyramids.

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
