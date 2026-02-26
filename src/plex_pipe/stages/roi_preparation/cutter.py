from typing import Any

import cv2
import numpy as np
import pandas as pd


class CoreCutter:
    """Extract rectangular or polygonal regions from images."""

    def __init__(self, margin: int = 0, mask_value: int = 0) -> None:
        """Initialize the CoreCutter.

        Args:
            margin: Padding pixels around each core.
            mask_value: Value to fill outside the polygon mask.
        """
        self.margin = margin
        self.mask_value = mask_value

    def extract_core(self, array: Any, row: pd.Series) -> np.ndarray:
        """Extract a single core from the source image.

        Args:
            array: Source image (NumPy or Dask array).
            row: Metadata describing the core. Must contain 'row_start',
                'row_stop', 'column_start', 'column_stop', and 'poly_type'.

        Returns:
            The extracted core image as a NumPy array.

        Raises:
            ValueError: If 'poly_type' is unknown.
        """
        # Read bbox coordinates
        y0 = int(row["row_start"])
        y1 = int(row["row_stop"])
        x0 = int(row["column_start"])
        x1 = int(row["column_stop"])

        # Apply margin & safety clipping
        img_height, img_width = array.shape
        y0m = max(0, y0 - self.margin)
        y1m = min(img_height, y1 + self.margin)
        x0m = max(0, x0 - self.margin)
        x1m = min(img_width, x1 + self.margin)

        # Extract subarray
        subarray = array[y0m:y1m, x0m:x1m]

        if row["poly_type"] == "rectangle":
            return subarray

        elif row["poly_type"] == "polygon":

            # Compute to numpy
            if hasattr(subarray, "compute"):  # Dask array check
                subarray = subarray.compute()

            # Load polygon coordinates and shift to local frame
            polygon = row["polygon_vertices"]  # assuming list of [y, x] pairs
            poly_rc_local = polygon - np.array([y0m, x0m])[None, :]
            poly_xy_int32 = np.round(poly_rc_local[:, [1, 0]]).astype(np.int32)

            # Apply mask
            mask = np.zeros(subarray.shape, np.uint8)
            cv2.fillPoly(mask, [poly_xy_int32], 1)
            subarray[mask == 0] = self.mask_value

            return subarray

        else:
            raise ValueError(f"Unknown poly_type: {row['poly_type']}")
