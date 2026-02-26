from __future__ import annotations

from typing import Any, Literal

import numpy as np
from loguru import logger
from pydantic import (
    ConfigDict,
    Field,
)

from plex_pipe.ops.base import (
    BaseOp,
    OutputType,
    ProcessorParamsBase,
)
from plex_pipe.ops.registry import register

################################################################################
# Object Segmenters
################################################################################


@register("object_segmenter", "instanseg")
class InstansegSegmenter(BaseOp):
    """Uses the InstanSeg deep learning model for segmentation."""

    OUTPUT_TYPE = OutputType.LABELS

    class Params(ProcessorParamsBase):
        """Parameters for the Instanseg segmenter."""

        model: Literal["fluorescence_nuclei_and_cells", "brightfield_nuclei"] = Field(
            "fluorescence_nuclei_and_cells",
            description="Choice of pre-trained InstanSeg model.",
        )
        pixel_size: float = Field(
            0.3, gt=0, description="Scaling factor for the segmentation."
        )
        resolve_cell_and_nucleus: bool = Field(
            default=True,
            description="Internal InstanSeg parameter. If True, both cell and nucleus masks will be returned. If False, only the cell mask will be returned.",
        )
        cleanup_fragments: bool = Field(
            default=True, description="Internal InstanSeg parameter."
        )
        clean_cache: bool = Field(
            default=False,
            description="If True, the CUDA cache is cleared after segmentation.",
        )
        normalise: bool = Field(
            default=True,
            description="Internal InstanSeg parameter. Controls whether the image is normalised.",
        )
        overlap: int = Field(
            default=80,
            description="Internal InstanSeg parameter. The overlap (in pixels) between tiles.",
        )

        # warn the user about any unrecognized parameters
        model_config = ConfigDict(extra="forbid")

    def __init__(self, **cfg: Any) -> None:
        """Initializes the InstanSeg segmenter.

        Args:
            **cfg: Configuration parameters passed to the Params model.
        """
        super().__init__(**cfg)

        if self.params.resolve_cell_and_nucleus:
            self.EXPECTED_OUTPUTS = 2
        else:
            self.EXPECTED_OUTPUTS = 1

        # import model
        from instanseg import InstanSeg

        self.model = InstanSeg(self.params.model, verbosity=1)

    def prepare_input(
        self, in_image: tuple[np.ndarray, ...] | list[np.ndarray] | np.ndarray
    ) -> np.ndarray:
        """Standardizes input images into (H, W, C) format.

        Args:
            in_image: Input image(s). Can be a single array (2D or 3D) or a sequence
                of 2D arrays.

        Returns:
            A numpy array formatted as (H, W, C).

        Raises:
            ValueError: If the input format is not supported.
        """
        if isinstance(in_image, tuple | list):
            in_image = np.stack(in_image, axis=-1)  # (H, W, C)
        elif isinstance(in_image, np.ndarray):
            if in_image.ndim == 2:
                in_image = in_image[..., np.newaxis]
            # 3D but has to transposed
            elif in_image.ndim == 3 and in_image.shape[0] < min(
                in_image.shape[1:]
            ):  # (C, H, W)
                in_image = np.moveaxis(in_image, 0, -1)

        else:
            raise ValueError(
                "Input must be a 2D/3D numpy array or a list of 2D arrays."
            )

        return in_image

    def run(self, *in_image: np.ndarray) -> list[np.ndarray]:
        """Runs the InstanSeg model on the provided image(s).

        Args:
            *in_image: One or more input image arrays.

        Returns:
            A list of segmentation masks (e.g., [nuclei, cells]).
        """
        # standardize input
        in_image = self.prepare_input(in_image)

        # Call InstanSeg
        labeled_output, _ = self.model.eval_medium_image(in_image, **dict(self.params))

        # extract result
        segm_arrays = [np.array(x).astype(np.int32) for x in labeled_output[0, :, :, :]]

        # clean cuda cache
        if self.params.clean_cache:
            import torch

            torch.cuda.empty_cache()

        return segm_arrays


@register("object_segmenter", "cellpose")
class Cellpose4Segmenter(BaseOp):
    """Uses the Cellpose deep learning model for segmentation."""

    EXPECTED_OUTPUTS = 1
    OUTPUT_TYPE = OutputType.LABELS

    class Params(ProcessorParamsBase):
        """Parameters for the Cellpose segmenter."""

        diameter: float | None = Field(
            30,
            gt=0,
            description="From Cellpose documentation: Scaling factor for the segmentation. Default size of cells 30 - segments well objects of size 10 -120.",
        )
        flow_threshold: float | None = Field(
            0.4,
            description="From Cellpose documentation: Maximum allowed flow error per mask (flow_threshold, default = 0.4). Increase it if too few ROIs are detected; decrease it if too many poor-quality ROIs appear.",
        )
        cellprob_threshold: float | None = Field(
            0,
            gt=-6,
            lt=6,
            description="From Cellpose documentation: Pixel threshold to define ROIs. Lower the threshold if too few ROIs are detected; raise it if too many—especially from dim regions.",
        )
        niter: int | None = Field(
            0,
            ge=0,
            description="From Cellpose documentation: If niter is None or 0, it scales with ROI size—use larger values (e.g., niter=2000) for longer ROIs.",
        )

        # warn the user about any unrecognized parameters
        model_config = ConfigDict(extra="forbid")

    def __init__(self, **cfg: Any) -> None:
        """Initializes the Cellpose segmenter.

        Args:
            **cfg: Configuration parameters passed to the Params model.
        """
        super().__init__(**cfg)

        # import model
        from cellpose import models

        self.model = models.CellposeModel(gpu=True)

    def prepare_input(
        self, in_image: tuple[np.ndarray, ...] | list[np.ndarray] | np.ndarray
    ) -> np.ndarray:
        """Standardizes input images for Cellpose.

        Args:
            in_image: Input image(s). Can be a single array or a sequence of arrays.

        Returns:
            A numpy array formatted as (C, H, W) or (H, W).

        Raises:
            ValueError: If inputs are not 2D arrays or if more than 2 channels are provided.
        """
        message = None
        if isinstance(in_image, tuple | list):
            for im in in_image:
                if im.ndim != 2:
                    message = "Only 2D arrays are accepted."
            if len(in_image) > 2:
                logger.warning(
                    "Cellpose will use only the first two provided channels."
                )
            in_image = np.stack(in_image[:2], axis=0)  # (C, H, W)

        elif isinstance(in_image, np.ndarray):
            if in_image.ndim != 2:
                message = "Only 2D arrays are accepted."

        if message:
            logger.error(message)
            raise ValueError(message)

        return in_image

    def run(self, *in_image: np.ndarray) -> np.ndarray:
        """Runs segmentation using Cellpose.

        Args:
            *in_image: One or more input image arrays. Can be a single image or a pair
                of images (e.g., nucleus and cytoplasm).

        Returns:
            The segmentation mask.
        """

        # prepare input
        in_image = self.prepare_input(in_image)

        # run segmentation
        mask, *_ = self.model.eval(in_image, **dict(self.params))

        return mask
