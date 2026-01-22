# 🔧 Configuration

The configuration file serves as the central blueprint for the PlexPipe analysis.
It provides parameters for all stages of the pipeline, ensuring reproducibility and ease of adjustment.

General info:
- pathways can operate

The pipeline configuration is divided into the following stages:

### General Settings

Global paths and analysis naming.

```yaml
# -----------------------------------------------------------------------------
# 1. General Settings
# -----------------------------------------------------------------------------
general:
  image_dir: "C:/path/to/images"           # Source directory for images
  analysis_name: "experiment_01"           # Name of the analysis run
  local_analysis_dir: "C:/analysis_out"    # Local output base directory
  remote_analysis_dir: "/mnt/analysis"     # Remote output base directory (if applicable)
  log_dir: null                            # Optional custom log directory
```

| Key                        | Type        | Description                                                             |
| -------------------------- | ----------- | ----------------------------------------------------------------------- |
| `image_dir`                | `str`       | Source directory with tiff images.                 |
| `analysis_name`            | `str`       | Name of the analysis run.                                              |


*   **General Settings**: Global paths and analysis naming.
*   **Core Detection**: Parameters for identifying cores in the whole-slide image.
*   **Core Cutting**: Settings for extracting and processing individual cores.
*   **Additional Elements**: Configuration for segmentation, mask building, and image transformation steps.
*   **Quality Control**: Settings for QC filtering.
*   **Quantification**: Parameters for extracting features from cells/objects.
*   **Storage**: Settings for Zarr storage (chunking, pyramids).
---

### Full configuration file example:

```yaml
# -----------------------------------------------------------------------------
# 1. General Settings
# -----------------------------------------------------------------------------
general:
  image_dir: "C:/path/to/images"           # Source directory for images
  analysis_name: "experiment_01"           # Name of the analysis run
  local_analysis_dir: "C:/analysis_out"    # Local output base directory
  remote_analysis_dir: "/mnt/analysis"     # Remote output base directory (if applicable)
  log_dir: null                            # Optional custom log directory

# -----------------------------------------------------------------------------
# 2. Core Detection
# -----------------------------------------------------------------------------
core_detection:
  detection_image: "DAPI"                  # Marker used for core detection
  core_info_file_path: null                # Optional path to pre-existing core metadata
  im_level: 6                              # Pyramid level to use for detection
  min_area: 5000                           # Minimum area for a core
  max_area: 50000                          # Maximum area for a core
  min_iou: 0.8                             # IoU threshold for shape matching
  min_st: 0.8                              # Score threshold
  min_int: 10                              # Minimum intensity threshold
  frame: 0                                 # Frame index

# -----------------------------------------------------------------------------
# 3. Core Cutting
# -----------------------------------------------------------------------------
core_cutting:
  cores_dir_tif: null                      # Optional override for temp TIFF storage
  cores_dir_output: null                   # Optional override for Zarr output
  include_channels: []                     # Force include specific channels (e.g. "001_DAPI")
  exclude_channels: []                     # Force exclude specific channels
  use_markers: ["DAPI", "CD45", "PanCK"]   # Restrict to specific markers
  ignore_markers: []                       # Ignore specific markers
  margin: 50                               # Margin around core bounding box (pixels)
  mask_value: 0                            # Background value for masks
  transfer_cleanup_enabled: true           # Cleanup Globus transfers
  core_cleanup_enabled: true               # Cleanup intermediate TIFFs

# -----------------------------------------------------------------------------
# 4. Additional Elements (Segmentation, etc.)
# -----------------------------------------------------------------------------
additional_elements:
  - category: "image_transformer"
    type: "normalize"
    input: "DAPI"
    output: "DAPI_norm"
    keep: false
    parameters: {}

  - category: "object_segmenter"
    type: "instanseg"
    input: "DAPI"
    output: "nucleus_mask"
    keep: true
    parameters:
      model_name: "nuclei"

# -----------------------------------------------------------------------------
# 5. Quality Control
# -----------------------------------------------------------------------------
qc:
  prefix: "qc_exclude"                     # Prefix for QC columns in AnnData

# -----------------------------------------------------------------------------
# 6. Quantification
# -----------------------------------------------------------------------------
quant:
  - name: "cell_quantification"
    masks:
      nucleus: "nucleus_mask"
    layer_connection: "nucleus_mask"

# -----------------------------------------------------------------------------
# 7. Storage Settings
# -----------------------------------------------------------------------------
sdata_storage:
  chunk_size: [1, 1024, 1024]              # Zarr chunk size (C, Y, X)
  max_pyramid_level: 3                     # Number of pyramid levels
  downscale: 2                             # Downscaling factor
```
