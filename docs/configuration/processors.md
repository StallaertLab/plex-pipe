# Available Processors
## Image Filter

### `denoise_with_median`

Applies a median filter to the image to remove noise.

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `disk_radius` (<class 'int'>, default=`3`): The radius of the disk-shaped kernel for the median filter.

### `mean_of_images`

Compute the mean of multiple image arrays.

*   **Inputs**: Variable
*   **Outputs**: 1
*   **Parameters**: None.

### `normalize`

Performs percentile-based normalization on the image.

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `low` (<class 'float'>, default=`1.0`): Lower percentile bound (0-100).
    *   `high` (<class 'float'>, default=`99.0`): Upper percentile bound (0-100).

## Mask Builder

### `blob`

Processes a mask to create blob-like shapes using morphological operations.

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `work_shape` (Tuple[int, int], default=`(250, 250)`): No description.
    *   `radius` (<class 'int'>, default=`5`): No description.

### `multiply`

Multiplies two masks (intersection).

*   **Inputs**: 2
*   **Outputs**: 1
*   **Parameters**: None.

### `ring`

Creates a ring-shaped mask around objects.

*   **Inputs**: 1
*   **Outputs**: 1
*   **Parameters**:
    *   `outer` (<class 'int'>, default=`7`): The outer radius of the ring in pixels.
    *   `inner` (<class 'int'>, default=`2`): The inner radius of the ring in pixels.

### `subtract`

Subtracts one mask from another (mask1 - mask2).

*   **Inputs**: 2
*   **Outputs**: 1
*   **Parameters**: None.

## Object Segmenter

### `cellpose`

Uses the Cellpose deep learning model for segmentation.

*   **Inputs**: Variable
*   **Outputs**: 1
*   **Parameters**:
    *   `diameter` (Optional[float], default=`30`): From Cellpose documentation: Scaling factor for the segmentation. Default size of cells 30 - segments well objects of size 10 -120.
    *   `flow_threshold` (Optional[float], default=`0.4`): From Cellpose documentation: Maximum allowed flow error per mask (flow_threshold, default = 0.4). Increase it if too few ROIs are detected; decrease it if too many poor-quality ROIs appear.
    *   `cellprob_threshold` (Optional[float], default=`0`): From Cellpose documentation: Pixel threshold to define ROIs. Lower the threshold if too few ROIs are detected; raise it if too many—especially from dim regions.
    *   `niter` (Optional[int], default=`0`): From Cellpose documentation: If niter is None or 0, it scales with ROI size—use larger values (e.g., niter=2000) for longer ROIs.

### `instanseg`

Uses the InstanSeg deep learning model for segmentation.

*   **Inputs**: Variable
*   **Outputs**: Variable
*   **Parameters**:
    *   `model` (Literal['fluorescence_nuclei_and_cells', 'brightfield_nuclei'], default=`fluorescence_nuclei_and_cells`): No description.
    *   `pixel_size` (<class 'float'>, default=`0.3`): Scaling factor for the segmentation.
    *   `resolve_cell_and_nucleus` (<class 'bool'>, default=`True`): No description.
    *   `cleanup_fragments` (<class 'bool'>, default=`True`): No description.
    *   `clean_cache` (<class 'bool'>, default=`False`): No description.
    *   `normalise` (<class 'bool'>, default=`True`): No description.
    *   `overlap` (<class 'int'>, default=`80`): No description.
