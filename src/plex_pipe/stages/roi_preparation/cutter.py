from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from loguru import logger

from plex_pipe.io.filesystem import read_ome_tiff, write_temp_tiff


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

    def cut_image(
        self,
        file_path: str | Path,
        channel: str,
        metadata_df: pd.DataFrame,
        temp_dir: str | Path,
    ) -> None:
        """Cut every ROI from one channel image and save each as a TIFF.

        Writes ``<temp_dir>/<roi_name>/<channel>.tiff`` for every row of
        ``metadata_df``. The image file is closed even if cutting fails.

        Args:
            file_path: Path to the source OME-TIFF file of this channel.
            channel: Name of the channel (used as the TIFF file name).
            metadata_df: ROI table; one row per ROI, with a ``roi_name``
                column and the columns used by :meth:`extract_core`.
            temp_dir: Directory for the per-ROI TIFFs.
        """
        full_img, store = read_ome_tiff(str(file_path))

        try:
            for _, row in metadata_df.iterrows():
                roi_id = row["roi_name"]
                roi_img = self.extract_core(full_img, row)
                write_temp_tiff(roi_img, roi_id, channel, str(temp_dir))
                logger.debug(f"Cut and saved ROI {roi_id}, channel {channel}.")
        finally:
            # Ensures file is closed even if something fails mid-cut
            if hasattr(store, "close"):
                store.close()
                logger.debug(f"Closed file handle for channel {channel}.")
