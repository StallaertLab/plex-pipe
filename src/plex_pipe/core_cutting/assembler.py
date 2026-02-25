import os

import numpy as np
import tifffile
from loguru import logger
from spatialdata import SpatialData
from spatialdata.models import Image2DModel


class CoreAssembler:
    """Assemble per-channel TIFF images into a unified SpatialData Zarr store."""

    def __init__(
        self,
        temp_dir: str,
        output_dir: str,
        max_pyramid_levels: int = 4,
        downscale: int = 2,
        chunk_size: tuple[int, int, int] = (
            1,
            256,
            256,
        ),  # SpatialData default chunk size
        allowed_channels: list[str] | None = None,
        cleanup: bool = False,
    ) -> None:
        """Initialize the assembler.

        Args:
            temp_dir (str): Directory containing temporary core subdirectories.
            output_dir (str): Destination directory for assembled Zarr stores.
            max_pyramid_levels (int, optional): Maximum number of multiscale
                pyramid levels. Set to 0 to disable.
            downscale (int, optional): Downsampling factor between levels.
            chunk_size (tuple[int, int, int], optional): Chunk dimensions
                (C, Y, X) for the Zarr array.
            allowed_channels (list[str] | None, optional): Channel names
                to process. If None, all found channels are used.
            cleanup (bool, optional): Whether to delete intermediate TIFF files
                after assembly.
        """
        self.temp_dir = temp_dir
        self.output_dir = output_dir
        self.max_pyramid_levels = max_pyramid_levels
        self.chunk_size = chunk_size
        self.downscale = downscale
        self.allowed_channels = allowed_channels
        self.cleanup = cleanup

    def assemble_core(self, core_id: str) -> str:
        """Assemble a single core from per-channel TIFFs into a SpatialData Zarr store.

        Args:
            core_id (str): Unique identifier for the core, corresponding to its
                subdirectory name.

        Returns:
            str: Path to the generated Zarr store.

        Raises:
            FileNotFoundError: If the core's temporary directory is missing.
            ValueError: If no valid TIFF files are found in the directory.
        """
        core_path = os.path.join(self.temp_dir, core_id)
        if not os.path.exists(core_path):
            raise FileNotFoundError(f"No temp folder found for core: {core_id}")

        # Collect and sort TIFFs
        channel_files = sorted(
            [
                f
                for f in os.listdir(core_path)
                if f.lower().endswith(".tiff") or f.lower().endswith(".tif")
            ]
        )
        if not channel_files:
            raise ValueError(f"No TIFFs found for core: {core_id}")

        used_channels = []

        # initialize object
        sdata = SpatialData()

        # save to drive
        output_path = os.path.join(self.output_dir, f"{core_id}.zarr")
        sdata.write(output_path, overwrite=True)

        for fname in channel_files:
            channel_name = os.path.splitext(fname)[0]

            # Skip if not in allowed list
            if self.allowed_channels and channel_name not in self.allowed_channels:
                continue

            full_path = os.path.join(core_path, fname)

            # Read base image
            base_img = tifffile.imread(full_path)

            # Parse into SpatialData model
            image_model = Image2DModel.parse(
                np.expand_dims(base_img, axis=0),
                dims=("c", "y", "x"),
                scale_factors=[self.downscale] * (self.max_pyramid_levels - 1),
                chunks=self.chunk_size,
            )

            sdata[channel_name] = image_model
            sdata.write_element(channel_name, overwrite=True)
            used_channels.append(channel_name)

            # release memory
            del sdata[channel_name]

        # log the info
        logger.info(f"ROI '{core_id}' assembled with channels: {used_channels}")

        if self.cleanup:
            self._cleanup_core_files(core_path, used_channels)

        return output_path

    def _cleanup_core_files(self, core_path: str, channels: list[str]) -> None:
        """Delete intermediate TIFF files for the specified channels.

        Args:
            core_path (str): Path to the core's temporary directory.
            channels (list[str]): List of channel names to delete.
        """
        for ch in channels:
            tiff_path = os.path.join(core_path, f"{ch}.tiff")
            try:
                os.remove(tiff_path)
                logger.debug(f"Deleted intermediate TIFF: {tiff_path}")
            except OSError as exc:
                logger.warning(f"Failed to delete {tiff_path}: {exc}")
