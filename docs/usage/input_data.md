## File Naming Convention

The pipeline expects OME-TIFF files to follow a specific naming convention (typical of processed CellDive data).
The filename is parsed to extract the **round number** and **marker name**.

Format: `[Prefix]_[Round].0.4_R000_[Dye]_[Marker]-[Suffix].ome.tif`

*   **Round**: Extracted from the second segment (e.g., `001` from `..._1.0.4_...`).
*   **Marker**:
    *   If the `[Dye]` segment contains "DAPI", the marker is set to `DAPI`.
    *   Otherwise, the marker is extracted from the `[Marker]` segment (everything before the first hyphen `-`).

**Example:**

*   File: `BLCA-1_1.0.4_R000_Cy3_pH2AX-AF555_FINAL_AFR_F.ome.tif`
*   **Round**: 1
*   **Marker**: pH2AX
*   **Channel Name**: `001_pH2AX`


## Sourcing Image Files

Original tiff files are required to divide into separate SpatialData objects in the Core Cutting step.

Core cutting supports two modes of operation:

* **Local mode**: Tiff files are available on the local filesystem.
* **Globus mode**: Tiff files are accessed remotely using Globus endpoints.

---

Differences in local vs. Globus mode come from how OME-TIFF files are sourced.

### 📰 Local Mode

In local mode, `image_dir` should point to a folder with accessible OME-TIFF files on disk.

```yaml
image_dir: "C:/path_to_image_directory"
```

---

### ☁️ Globus Mode

In Globus mode, you must also specify the path to a Globus configuration directory. The `image_dir` field should reflect the remote directory on the Globus endpoint:

```yaml
image_dir: "/my_globus/path_to_image_directory"
```

This allows the pipeline to discover and transfer files on demand via Globus.

**Work in progress explain Globus settings file.**
