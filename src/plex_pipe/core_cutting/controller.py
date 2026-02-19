import os
from pathlib import Path

import pandas as pd
from loguru import logger

from plex_pipe.core_cutting.assembler import CoreAssembler
from plex_pipe.core_cutting.cutter import CoreCutter
from plex_pipe.core_cutting.input_strategy import FileAvailabilityStrategy
from plex_pipe.utils.file_utils import read_ome_tiff, write_temp_tiff


class RoiPreparationController:
    """Coordinate cutting and assembly of cores from multiplex images."""

    def __init__(
        self,
        metadata_df: pd.DataFrame,
        file_strategy: FileAvailabilityStrategy,
        temp_dir: str,
        output_dir: str,
        margin: int = 0,
        mask_value: int = 0,
        max_pyramid_levels: int = 3,
        chunk_size: tuple[int, int, int] = (1, 256, 256),
        downscale=2,
        temp_roi_delete: bool = True,
    ) -> None:
        """Initialize the controller.

        Args:
            metadata_df (pandas.DataFrame): Table describing each core.
            temp_dir (str): Directory for temporary core files.
            output_dir (str): Destination for assembled ``.zarr`` outputs.
            file_strategy (FileAvailabilityStrategy): Strategy used to obtain
                image files.
            margin (int, optional): Pixels of padding around each core.
            mask_value (int, optional): Fill value for masked regions.
            max_pyramid_levels (int, optional): Number of pyramid levels.
            chunk_size (tuple[int, int, int], optional): Chunk size for the
                data storage.
            temp_roi_delete (bool, optional): Remove intermediate TIFFs
                after assembly.
        """

        self.metadata_df = metadata_df
        self.file_strategy = file_strategy
        self.temp_dir = temp_dir
        self.output_dir = output_dir
        self.margin = margin
        self.mask_value = mask_value

        os.makedirs(output_dir, exist_ok=True)

        self.cutter = CoreCutter(margin=margin, mask_value=mask_value)
        self.assembler = CoreAssembler(
            temp_dir=temp_dir,
            output_dir=output_dir,
            max_pyramid_levels=max_pyramid_levels,
            chunk_size=chunk_size,
            downscale=downscale,
            allowed_channels=list(self.file_strategy.channel_map.keys()),
            cleanup=temp_roi_delete,
        )

        self.completed_channels = []
        self.completed_cores = []

    def cut_channel(self, channel, file_path):
        """Cut all cores from a single channel image.

        Args:
            channel (str): Name of the channel being processed.
            file_path (str | Path): Path to the OME-TIFF file.
        """

        full_img, store = read_ome_tiff(str(file_path))

        try:
            for _, row in self.metadata_df.iterrows():
                core_id = row["roi_name"]
                core_img = self.cutter.extract_core(full_img, row)
                write_temp_tiff(core_img, core_id, channel, self.temp_dir)
                logger.debug(f"Cut and saved ROI {core_id}, channel {channel}.")
        finally:
            # Ensures file is closed even if something fails mid-cut
            if hasattr(store, "close"):
                store.close()
                logger.debug(f"Closed file handle for channel {channel}.")

    def run(self, poll_interval: float = 10.0) -> None:
        """Process all channels and assemble cores.

        This method blocks until all channels have been processed and the
        corresponding cores have been assembled.
        """

        logger.info("Starting ROI preparation controller...")

        for channel, path in self.file_strategy.yield_ready_channels():

            # Process the newly arrived image
            logger.info(f"Channel {channel} ready. Starting cutting...")
            self.cut_channel(channel, path)

            # Cleanup - Strategy handles the temp file
            self.file_strategy.cleanup(Path(path))
            self.completed_channels.append(channel)

        logger.info("All channels processed. Starting assembly...")

        # Assemble cores
        for _, row in self.metadata_df.iterrows():
            core_id = row["roi_name"]
            self.assembler.assemble_core(core_id)

        logger.info("All cores assembled. Controller run complete.")
