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

Every configuration carries a **`schema_version`** at the top of the file, recording which version of the config format the file was written for. **The current schema version is `"2.0"`.**

```yaml
schema_version: "2.0"
```

The version has two parts, `MAJOR.MINOR`, and is independent of the PlexPipe package version:

* **MAJOR** changes when settings are moved, renamed or removed, so that an older file would no longer load as it is. PlexPipe upgrades such files automatically (see below).
* **MINOR** changes when new optional settings are added. Older files load unchanged.

Keep the quotes: without them, YAML reads `2.10` as the number `2.1`.

**Loading an older config.** If you load a file written for an older schema (for example `schema_version: 1`), or one with no `schema_version` (treated as the original version `0`), PlexPipe upgrades it in memory automatically and logs what it changed. Your pipeline runs without you editing anything by hand.

**Saving the upgraded file.** The automatic upgrade does not modify your file on disk. To write out the upgraded version, call `migrate_config`:

```python
import plex_pipe
plex_pipe.migrate_config("analysis_old.yaml")  # writes analysis_old_v2.yaml
```

This writes a new file next to the original (the name gets `_v2`, after the current MAJOR version) and leaves your original untouched. To choose the output file yourself, give its path as the second argument:

```python
plex_pipe.migrate_config("analysis_old.yaml", "analysis.yaml")
```

If the file is already at the current schema, nothing is written.

**A config that is too new.** If you load a config written for a newer MAJOR version than your installed PlexPipe understands, loading stops with a clear error asking you to upgrade PlexPipe. If only the MINOR version is newer (e.g. `"2.1"` with a PlexPipe that knows `"2.0"`), the config loads with a warning: settings your PlexPipe does not know yet would be ignored.

**What changed in each version** is listed in the [Schema Changelog](schema_changelog.md).

The full set of fields for the current schema is documented in the [Reference](reference.md).

---
## Config Snapshots

Each pipeline script (`02_cut_rois.py`, `04_segment.py`, `05_quantify.py`) saves the config it ran with to the `configs/` folder of the analysis directory. Your own config file is not changed.

* Each distinct config is saved once, as `configs/config_<hash>.yaml`, where `<hash>` is a short fingerprint of its content (e.g. `config_7837c2df.yaml`). Steps run with the same config share one file; changing any setting gives a new file.
* The snapshot is the config as used, already upgraded to the current schema. You can load it with `plex_pipe.load_config` to repeat a run.
* Each step's log names the snapshot it used, together with the source file, the folder the run started from, the PlexPipe version and the schema version.

Notebooks don't save snapshots automatically. You can save one with:

```python
plex_pipe.save_config_snapshot(config)
```

---
## Path Format

When entering file paths in this configuration file, always use the forward slash (/) as the folder separator, even on Windows.
The backslash (\\) is a "special character" in YAML. Using it can cause errors or require you to "double-up" your slashes (e.g., C:\\\Users).

Correct: C:/path/to/images Avoid: C:\path\to\images.

---
## Examples

Full example configuration files can be found in the [examples folder](https://github.com/StallaertLab/plex-pipe/tree/main/examples).
