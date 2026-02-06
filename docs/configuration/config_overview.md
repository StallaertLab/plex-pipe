# 🔧 Configuration

The configuration file serves as the central blueprint for the PlexPipe analysis.
It provides parameters for all stages of the pipeline divided into sections corresponding to the [analysis steps](../what_is_plexpipe.md).

This configuration is defined in a YAML file; you can find a deep dive into the syntax at [YAML official website](https://yaml.org/about/), but the description and examples below should be more than enough to get you started.

---
## Reproducibility and Provenance

To maintain a reliable audit trail, avoid modifying parameters once a step has been completed. The configuration file, paired with the resulting log files, serves as the formal documentation for the pipeline execution.

---
## Config Validation

To ensure your configuration is valid, the system validates your input against a predefined schema.

Validation Rules:

*   **Required Fields**: These must be present in your configuration file. If a required field is missing, the application will return an error.

*   **Optional Fields**: These are labeled as (optional). You can choose to:

    * Omit them entirely (the system will use its default behavior).
    * Set them to null (or ~) to explicitly signify no custom value.
    * Provide a custom value to override the default.

---
## Path Format

When entering file paths in this configuration file, always use the forward slash (/) as the folder separator, even on Windows.
The backslash (\\) is a "special character" in YAML. Using it can cause errors or require you to "double-up" your slashes (e.g., C:\\\Users).

Correct: C:/path/to/images Avoid: C:\path\to\images.

---
## Examples

Full example configuration files can be found in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples).
