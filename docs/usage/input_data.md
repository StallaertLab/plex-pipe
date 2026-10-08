# Input Data

## What you need

* **One image file per channel**: TIFF or OME-TIFF (`.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`), flat or pyramidal.
* **All channel files in one folder** (`image_dir` in the config YAML file), without sub-folders.
* **Registered images**: ROIs are cut at the same coordinates from every channel, so all channels must be aligned to each other.

For every file, PlexPipe needs to know **which marker it contains**. Marker names become the image layer names in the analysis.

Multiplexed experiments often contain more images than you want to analyse: a marker may have been imaged more than once (e.g. DAPI in every round, or a re-stain), or some images should be skipped altogether. PlexPipe lets you set **selection rules** in the configuration to decide which image is kept for each marker (by default, the latest round of each marker and the earliest round of DAPI). Because these rules work with rounds, PlexPipe also needs to know in which imaging **round** each file was acquired.

You can provide this information in two ways:

* **Cell DIVE data** is supported out of the box: marker and round are read from the original Cell DIVE file names.
* **Any other TIFFs** can be used by providing a short CSV (a *channel manifest*) that lists each file with its marker and, optionally, its round.

The CSV format and the rules for keeping and skipping images are described in [Channel Selection](../configuration/channel-selection.md).

---

## Sourcing Image Files

The original TIFF files are needed in the [ROI cutting step](../analysis_steps/02_roi_cutting.md), where they are divided into separate SpatialData objects. The files can be sourced in two ways:

* **Local mode**: TIFF files are available on the local filesystem.
* **Globus mode**: TIFF files are accessed remotely through [Globus](https://www.globus.org/) endpoints. Only the selected channels are transferred.

For details of setting up Globus see [Globus Setup](../usage/globus.md).

All downstream steps are performed on locally available SpatialData objects.
