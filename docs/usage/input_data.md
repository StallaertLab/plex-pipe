## Sourcing Image Files

### File Naming Convention

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
