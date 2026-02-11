from __future__ import annotations

import numpy as np
from pydantic import Field, field_validator, model_validator
from scipy import ndimage as ndi
from skimage.morphology import closing, disk, opening
from skimage.segmentation import expand_labels, find_boundaries
from skimage.transform import resize

from plex_pipe.processors.base import (
    BaseOp,
    OutputType,
    ProcessorParamsBase,
)
from plex_pipe.processors.registry import register

################################################################################
# Mask Builders
################################################################################


@register("mask_builder", "subtract")
class SubtractionBuilder(BaseOp):
    """Subtracts one mask from another (mask1 - mask2).

    Common Use Cases:

    * Cytoplasm: To capture the cytoplasmic region of a cell, you can subtract the nuclear mask from the whole cell mask.
    """

    EXPECTED_INPUTS = 2
    EXPECTED_OUTPUTS = 1
    OUTPUT_TYPE = OutputType.LABELS

    def run(self, mask_cell, mask_nucleus):
        if mask_cell.shape != mask_nucleus.shape:
            raise ValueError("Source masks must have the same shape for subtraction.")
        result = mask_cell.copy()
        result[mask_nucleus > 0] = 0  # zero out regions where mask_nucleus is present
        return result


###############################################################################
###############################################################################


@register("mask_builder", "multiply")
class MultiplicationBuilder(BaseOp):
    """Multiplies two masks (intersection)."""

    EXPECTED_INPUTS = 2
    EXPECTED_OUTPUTS = 1
    OUTPUT_TYPE = OutputType.LABELS

    def run(self, mask1, mask2):
        if mask1.shape != mask2.shape:
            raise ValueError("Source masks must have the same shape.")
        result = mask1 * mask2
        return result


###############################################################################
###############################################################################
@register("mask_builder", "ring")
class RingBuilder(BaseOp):
    """Creates annular (ring-shaped) regions of interest from an existing labeled mask.
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
    """

    EXPECTED_INPUTS = 1
    EXPECTED_OUTPUTS = 1
    OUTPUT_TYPE = OutputType.LABELS

    ######################################################
    # current implementation is super slow and not memory efficient
    ######################################################

    class Params(ProcessorParamsBase):
        """Parameters for creating a ring mask."""

        rad_bigger: int = Field(
            7,
            description="Outer boundary radius (px). Positive expands, negative erodes.",
        )
        rad_smaller: int = Field(
            2,
            description="Inner boundary radius (px). Positive expands, negative erodes.",
        )

        @model_validator(mode="after")
        def check_radii_are_valid(self):
            """Ensures the outer radius is strictly greater than the inner radius."""
            if self.rad_bigger <= self.rad_smaller:
                raise ValueError(
                    f"outer radius ({self.rad_bigger}) must be strictly greater than inner radius ({self.rad_smaller})"
                )
            return self

    def run(self, mask):
        r_large = self.params.rad_bigger
        r_small = self.params.rad_smaller

        # 1. Precompute distance map if erosion is needed
        dist_map = None
        if r_large < 0 or r_small < 0:
            # find_boundaries(mask) is True at any label interface OR background interface
            # We invert it (~) so that boundaries are 0 and object interiors are 1
            boundaries = find_boundaries(mask, mode="thick")
            # distance_transform_edt calculates distance to the nearest 0 (the boundaries)
            dist_map = ndi.distance_transform_edt(~boundaries)

        def get_bound(radius):
            if radius == 0:
                return mask.copy()
            elif radius > 0:
                return expand_labels(mask, radius)
            else:
                # Mask pixels that are too close to ANY boundary (including neighbor labels)
                return np.where(dist_map >= abs(radius), mask, 0)

        mask_larger = get_bound(r_large)
        mask_smaller = get_bound(r_small)

        mask_larger[mask_smaller > 0] = 0
        return mask_larger


###############################################################################
###############################################################################
@register("mask_builder", "blob")
class BlobBuilder(BaseOp):
    """
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
    """

    EXPECTED_INPUTS = 1
    EXPECTED_OUTPUTS = 1
    OUTPUT_TYPE = OutputType.LABELS

    class Params(ProcessorParamsBase):
        """Parameters for the blob creation operation."""

        work_shape: tuple[int, int] = Field(
            (250, 250),
            description="The resolution at which the blob is calculated. Lowering this value makes the processor more 'forgiving' of gaps but coarser in detail.",
        )
        radius: int = Field(
            5,
            gt=0,
            description="The size of the disk used to open and close the mask. Larger values result in smoother, more rounded blobs.",
        )

        @field_validator("work_shape")
        def check_positive_dimensions(cls, v: tuple[int, int]) -> tuple[int, int]:
            """Ensures both dimensions in work_shape are positive integers."""
            if not (v[0] > 0 and v[1] > 0):
                raise ValueError(
                    "Both dimensions in 'work_shape' must be positive integers."
                )
            return v

    def run(self, source):

        orig_shape = source.shape
        binary_mask = source > 0

        # Downsample mask for robust morphological cleaning
        resized_mask = (
            resize(
                binary_mask.astype(int),
                self.params.work_shape,
                order=1,
                preserve_range=True,
            )
            > 0
        )

        # Morphological opening & closing
        selem = disk(self.params.radius)
        blob_mask = opening(resized_mask, selem)
        blob_mask = closing(blob_mask, selem)

        # Upsample to original shape
        blob_mask = (
            resize(
                blob_mask.astype(float),
                orig_shape,
                order=1,
                preserve_range=True,
            )
            > 0
        )
        return blob_mask.astype("int")
