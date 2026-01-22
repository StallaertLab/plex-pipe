# 🎯 Channel Selection Logic

## Terminology

To understand how channels are selected, it is important to distinguish between:

*   **Marker Name**: The biological target being imaged (e.g., `DAPI`, `CD44`, `pRB`). This is derived from the filename.
*   **Channel Name**: The unique identifier for a specific image acquisition, combining the **round number** and the **marker name** (e.g., `001_DAPI`, `002_CD44`). This format (`{round:03d}_{marker}`) allows the pipeline to distinguish between the same marker imaged in different rounds.

---

The pipeline supports fine-grained control over which imaging channels are included in processing. This is essential because:

- The same marker may be imaged multiple times across rounds (e.g., re-staining or optimization).
- DAPI is typically acquired in every round for registration but usually only one version should be kept for the analysis.

The selection process follows this logic:

### 1. **Default Behavior (if no overrides)**
- For each marker imaged in multiple rounds, the **latest round** is used by default.
- For DAPI, only `001_DAPI` is included unless specified otherwise.

### 2. **Using `include_channels`**
- This is a list of channel names like `002_CD44`, `001_DAPI`.
- If set, only these channels are included for a given marker — **they override automatic selection**.
- Use this to **force inclusion of earlier rounds** or **include duplicates** for comparison.

### 3. **Using `exclude_channels`**
- This is a list of channel names to skip.
- If `include_channels` is not set, `exclude_channels` can be used to **remove undesired versions**.
- Example: to exclude `003_pRB` in favor of earlier versions (or none).

### 4. **Using `use_markers`**
- This is a list of **base marker names** (like `DAPI`, `pRB`, `CD44`) **after stripping the round prefix**.
- After all other filtering, `use_markers` is applied as a final filter.
- Use it to **narrow the final channel set to specific markers**, regardless of which round was selected.

### 5. **Using `ignore_markers`**
- This is a list of **base marker names** to exclude from the final set.
- It is applied after `use_markers`.
- Use it to **discard specific markers** entirely (e.g. if a marker failed quality control across all rounds).

---

## Examples

### Example 1: Default automatic selection
```yaml
include_channels: []
exclude_channels: []
use_markers: []
```

* Keeps only the **latest round per marker**, and `001_DAPI`.

---

### Example 2: Force earlier pRB round to be used

```yaml
include_channels: ["001_pRB"]
use_markers: []
```

* `001_pRB` is used even if `003_pRB` exists.

---

### Example 3: Exclude a problematic round

```yaml
exclude_channels: ["003_CD44"]
```

* Automatically selects an earlier round (if available) for CD44.

---

### Example 4: Only process DAPI and CD44

```yaml
use_markers: ["DAPI", "CD44"]
```

* Filters final output to only include these two base markers.

---

### Conflicts and Priority

* If a channel is listed in both `include_channels` and `exclude_channels`, a `ValueError` is raised.
* `use_channels` is applied **last**, on the base names after channel selection.
