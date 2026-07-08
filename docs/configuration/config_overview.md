# 🔧 Configuration

The configuration file serves as the central blueprint for the PlexPipe analysis.
It provides parameters for all stages of the pipeline divided into sections corresponding to the [analysis steps](../analysis_steps/00_steps_overview.md).

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
## Schema Version and Migration

Every configuration carries a **`schema_version`** at the top of the file, recording which version of the config format the file was written for. **The current schema version is `1`.**

This version is a plain incrementing counter, independent of the PlexPipe package version. It changes only when the config *format* changes, which is rare, so most releases leave it untouched.

**Loading an older config.** If you load a file written for an older schema, or one with no `schema_version` (treated as the original version `0`), PlexPipe upgrades it in memory automatically and logs what it changed. Your pipeline runs without you editing anything by hand.

**Saving the upgraded file.** The automatic upgrade does not modify your file on disk. To write out the upgraded version, call `migrate_config`:

```python
import plex_pipe
plex_pipe.migrate_config("analysis_old.yaml")  # writes analysis_old_v1.yaml
```

By default this writes a new file and leaves your original untouched. Pass a second argument to set a specific output path.

**A config that is too new.** If you load a config written for a schema newer than your installed PlexPipe understands, loading stops with a clear error asking you to upgrade PlexPipe.

The full set of fields for the current schema is documented in the [Reference](reference.md).

---
## Path Format

When entering file paths in this configuration file, always use the forward slash (/) as the folder separator, even on Windows.
The backslash (\\) is a "special character" in YAML. Using it can cause errors or require you to "double-up" your slashes (e.g., C:\\\Users).

Correct: C:/path/to/images Avoid: C:\path\to\images.

---
## Examples

Full example configuration files can be found in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples).
