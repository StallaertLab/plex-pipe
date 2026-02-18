# Available Processors
Processors are modular operations used within [Step 04: Image Processing](../analysis_steps/04_image_processing.md).

---

---
## Image Enhancers

---

---

### `denoise_with_median`

Applies a median filter to the image.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `disk_radius` (<class 'int'>default=`3`): The radius of the disk-shaped kernel for the median filter.
</details>
---

### `mean_of_images`

Compute the mean of multiple image arrays.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: Variable
*   **Outputs**: 1
*   **Parameters**: None.
</details>
---

### `normalize`

Performs percentile-based normalization on the image.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `low` (<class 'float'>default=`1.0`): Lower percentile bound (0-100).
    *   `high` (<class 'float'>default=`99.0`): Upper percentile bound (0-100).
</details>
---


---
## Mask Builders

---

---

### `blob`

Generates a coarse, smoothed binary mask (a 'blob') to define valid tissue regions.
The input can be a marker image or a segmentation mask, and the output is a binary mask
where 1 indicates tissue presence and 0 indicates background.

It creates a simplified representation of the input by:

* **Binarization**: Converting the input to a binary format (signal higher than 0 becomes 1).

* **Rescaling**: Downsampling the input to a lower resolution (`work_shape`) to blur individual small detections into aggregate clusters.

* **Morphological Opening**: Removing small, isolated noise clusters that do not form a significant mass.

* **Morphological Closing**: Fusing nearby clusters into solid 'blobs' and filling internal holes.

* **Rescaling**: Upsampling back to the original resolution to be used as a bitmask.

Common Use Cases:

* **Tissue Masking**: Run this on an initial segmentation mask to identify the broad footprint of the tissue.
The resulting blob mask can then be multiplied with the original segmentation to
automatically "clip" or "clean" any false-positive detections occurring in the
very sparse regions beyond the actual tissue boundary.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `work_shape` (tuple[int, int]default=`(250, 250)`): The resolution at which the blob is calculated. Lowering this value makes the processor more 'forgiving' of gaps but coarser in detail.
    *   `radius` (<class 'int'>default=`5`): The size of the disk used to open and close the mask. Larger values result in smoother, more rounded blobs.
</details>
---

### `multiply`

Multiplies two masks (intersection).

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 2
*   **Outputs**: 1
*   **Parameters**: None.
</details>
---

### `ring`

Creates annular (ring-shaped) regions of interest from an existing labeled mask.
It is topology-aware: it ensures that even when objects are packed closely together,
the rings respect the boundaries of neighboring labels rather than overlapping or merging.
It handles both expansion and contraction.

Common Use Cases:

* The "Nuclear Envelope" Ring:
To capture the region immediately surrounding a nucleus,
set rad_bigger=3 and rad_smaller=0.
This starts the ring at the nuclear boundary and extends it 5 pixels into the cytoplasm.

* The "Internal Cortical" Ring:
To capture the area just inside the cell membrane,
set rad_bigger=0 and rad_smaller=-3.
This keeps the original boundary and "hollows out" the center.

* The "Cytoplasmic Gap Ring":
To capture an area that doesn't touch the original label (a "halo"),
set rad_bigger=7 and rad_smaller=2.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `rad_bigger` (<class 'int'>default=`7`): Outer boundary radius (px). Positive expands, negative erodes.
    *   `rad_smaller` (<class 'int'>default=`2`): Inner boundary radius (px). Positive expands, negative erodes.
</details>
---

### `subtract`

Subtracts one mask from another (mask1 - mask2).

Common Use Cases:

* Cytoplasm: To capture the cytoplasmic region of a cell, you can subtract the nuclear mask from the whole cell mask.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: 2
*   **Outputs**: 1
*   **Parameters**: None.
</details>
---


---
## Object Segmenters

---

---

### `cellpose`

Uses the Cellpose deep learning model for segmentation.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: Variable
*   **Outputs**: 1
*   **Parameters**:
    *   `diameter` (float | Nonedefault=`30`): From Cellpose documentation: Scaling factor for the segmentation. Default size of cells 30 - segments well objects of size 10 -120.
    *   `flow_threshold` (float | Nonedefault=`0.4`): From Cellpose documentation: Maximum allowed flow error per mask (flow_threshold, default = 0.4). Increase it if too few ROIs are detected; decrease it if too many poor-quality ROIs appear.
    *   `cellprob_threshold` (float | Nonedefault=`0`): From Cellpose documentation: Pixel threshold to define ROIs. Lower the threshold if too few ROIs are detected; raise it if too many—especially from dim regions.
    *   `niter` (int | Nonedefault=`0`): From Cellpose documentation: If niter is None or 0, it scales with ROI size—use larger values (e.g., niter=2000) for longer ROIs.
</details>
---

### `instanseg`

Uses the InstanSeg deep learning model for segmentation.

<details markdown="1">
<summary><b>Technical Specs</b></summary>

*   **Inputs**: Variable
*   **Outputs**: Variable
*   **Parameters**:
    *   `model` (Literal['fluorescence_nuclei_and_cells', 'brightfield_nuclei']default=`fluorescence_nuclei_and_cells`): Choice of pre-trained InstanSeg model.
    *   `pixel_size` (<class 'float'>default=`0.3`): Scaling factor for the segmentation.
    *   `resolve_cell_and_nucleus` (<class 'bool'>default=`True`): Internal InstanSeg parameter. If True, both cell and nucleus masks will be returned. If False, only the cell mask will be returned.
    *   `cleanup_fragments` (<class 'bool'>default=`True`): Internal InstanSeg parameter.
    *   `clean_cache` (<class 'bool'>default=`False`): If True, the CUDA cache is cleared after segmentation.
    *   `normalise` (<class 'bool'>default=`True`): Internal InstanSeg parameter. Controls whether the image is normalised.
    *   `overlap` (<class 'int'>default=`80`): Internal InstanSeg parameter. The overlap (in pixels) between tiles.
</details>
---
