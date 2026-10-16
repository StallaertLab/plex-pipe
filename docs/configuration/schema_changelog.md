# Schema Changelog

All notable changes to the config file format, by `schema_version`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 2.0 (PlexPipe 0.1.0)

### Added

- `channels` section.
- `channels.file_naming`.
- `channels.manifest`.
- `channels.earliest_round_markers`.

### Changed

- **Breaking:** `include_channels`, `exclude_channels`, `use_markers` and `ignore_markers` moved from `roi_cutting` to `channels`.
- `schema_version` format changed to `"MAJOR.MINOR"`.
- Contradicting selection settings in `channels` are rejected.
- Unknown keys are rejected, so a misspelled key stops loading instead of being ignored. A config with a newer MINOR version still loads; keys this version does not know are ignored with a warning.

## 1

### Changed

- `general.local_analysis_dir` renamed to `general.analysis_dir`.
- `core_detection` renamed to `roi_definition`; `core_info_file_path` renamed to `roi_info_file_path`.
- `core_cutting` renamed to `roi_cutting`; `cores_dir_tif`, `cores_dir_output` and `core_cleanup_enabled` renamed to `roi_dir_tif`, `roi_dir_output` and `roi_cleanup_enabled`.
- `additional_elements`: categories `image_filter` and `image_transformer` merged into `image_enhancer`; ring builder parameters `outer` and `inner` renamed to `rad_bigger` and `rad_smaller`.
- `quant.qc_to_layer` renamed to `quant.qc_to_table`.

### Removed

- `general.remote_analysis_dir`.
- SAM2 settings in `core_detection`.

## 0

Initial unversioned format.
