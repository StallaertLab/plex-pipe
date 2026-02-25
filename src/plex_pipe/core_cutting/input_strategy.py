import time
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from pathlib import Path

from globus_sdk import (
    GlobusAPIError,
    TransferData,
)
from loguru import logger

from plex_pipe.core_cutting.channel_scanner import discover_channels
from plex_pipe.utils.config_schema import AnalysisConfig
from plex_pipe.utils.globus_utils import (
    GlobusConfig,
    create_globus_tc,
)

RETRYABLE_STATUSES = {502, 503, 504}
MAX_TRIES = 6
BASE_DELAY = 2.0  # seconds
MAX_DELAY = 60.0  # seconds

ChannelMap = Mapping[str, str]


class FileAvailabilityStrategy(ABC):
    """Strategy interface for ensuring image files are available."""

    config: AnalysisConfig
    channel_map: ChannelMap

    @abstractmethod
    def __init__(self, config: AnalysisConfig) -> None:
        """Initialize the strategy.

        Args:
            config: Analysis configuration object.
        """
        self.config = config

    @abstractmethod
    def yield_ready_channels(self) -> Iterator[tuple[str, str | Path]]:
        """Yield (channel, local_path) tuples as they become available."""

    @abstractmethod
    def cleanup(self, path: Path) -> None:
        """Remove or close the given file path."""


class GlobusFileStrategy(FileAvailabilityStrategy):
    """Fetch files from a remote Globus endpoint."""

    def __init__(
        self,
        config: AnalysisConfig,
        gc: GlobusConfig,
        cleanup_enabled: bool = True,
    ) -> None:
        """Initialize the GlobusFileStrategy.

        Args:
            config: Analysis configuration object.
            gc: Globus configuration object.
            cleanup_enabled: Whether to remove local files after processing.
        """
        # build channel map
        super().__init__(config)
        self.gc = gc
        self.tc = create_globus_tc(gc.client_id, gc.transfer_tokens)

        self.channel_map = discover_channels(
            self.config.general.image_dir,
            include_channels=self.config.roi_cutting.include_channels,
            exclude_channels=self.config.roi_cutting.exclude_channels,
            use_markers=self.config.roi_cutting.use_markers,
            ignore_markers=self.config.roi_cutting.ignore_markers,
            gc=self.gc,
        )

        self.pending_tasks: list[str] = []
        self.yielded_channels: set[str] = set()
        self.cleanup_enabled = cleanup_enabled

        # build transfer map
        self.build_transfer_map()

        # look up channel by the remote path Globus reports
        self._remote_to_channel = {
            remote: ch for ch, (remote, local) in self.transfer_map.items()
        }

    def build_transfer_map(self) -> None:
        """Create a mapping between channel names and transfer paths."""

        base = self.config.temp_dir

        transfer_map = {
            ch: (
                str(Path(remote).as_posix()),
                str(self.gc.destination.local_to_globus(base / Path(remote).name)),
            )
            for ch, remote in self.channel_map.items()
        }

        self.transfer_map = transfer_map

    def submit_all_transfers(self, batch_size: int = 1) -> None:
        """Submit file transfer tasks to Globus.

        Args:
            batch_size: Number of files to include in a single transfer task.

        Raises:
            RuntimeError: If the Globus API submission fails.
        """

        channels = list(self.transfer_map.items())

        # Split channels into batches of given size
        for i in range(0, len(channels), batch_size):
            batch = channels[i : i + batch_size]

            td = TransferData(
                source_endpoint=self.gc.source.collection_id,
                destination_endpoint=self.gc.destination.collection_id,
                label=f"PlexPipe Batch {i//batch_size + 1}",
                sync_level="checksum",
            )

            for _channel, (remote, local) in batch:
                td.add_item(remote, local)

            # Submit the batch with SDK v4
            try:
                result = self.tc.submit_transfer(td)
                self.pending_tasks.append(result["task_id"])
                logger.info(
                    f"Submitted batch {i//batch_size + 1} (Task: {result['task_id']})"
                )
            except GlobusAPIError as e:
                raise RuntimeError(f"Failed to submit Globus batch: {e}") from e

    def yield_ready_channels(self) -> Iterator[tuple[str, Path]]:
        """Monitor pending transfers and yield channels as they complete.

        Yields:
            Tuple of (channel_name, local_file_path).

        Raises:
            GlobusAPIError: If a non-retryable Globus API error occurs.
        """
        remaining_channels = set(self.channel_map.keys())
        self.yielded_channels = set()

        while remaining_channels:
            for task_id in self.pending_tasks:
                try:
                    # SDK v4 method name
                    for xfer in self.tc.task_successful_transfers(task_id):
                        remote_path = xfer["source_path"]
                        channel = self._remote_to_channel.get(remote_path)

                        if channel and channel not in self.yielded_channels:
                            self.yielded_channels.add(channel)
                            remaining_channels.remove(channel)
                            local_path = self.gc.destination.globus_to_local(
                                self.transfer_map[channel][1]
                            )
                            yield channel, local_path

                except GlobusAPIError as e:
                    # Handle the "still in progress" error
                    if e.http_status == 400 and "is still in progress" in e.message:
                        continue
                    raise e

                if remaining_channels:
                    time.sleep(10)

    def cleanup(self, path: Path, force: bool = False) -> None:
        """Remove the specified file if cleanup is enabled.

        Args:
            path: Path to the file to remove.
            force: If True, perform cleanup even if cleanup_enabled is False.
        """

        if not self.cleanup_enabled and not force:
            logger.info(f"Skipping cleanup for {path}; cleanup is disabled.")
            return

        try:
            if path.exists():
                path.unlink()
                logger.info(f"Cleaned up file: {path}")
        except OSError as exc:
            logger.warning(f"Cleanup failed for {path}: {exc}")


class LocalFileStrategy(FileAvailabilityStrategy):
    """Strategy that relies on files already present locally."""

    def __init__(
        self,
        config: AnalysisConfig,
    ) -> None:
        """Initialize the LocalFileStrategy.

        Args:
            config: Analysis configuration object.
        """
        self.gc = None
        super().__init__(config)

        self.channel_map = discover_channels(
            self.config.general.image_dir,
            include_channels=self.config.roi_cutting.include_channels,
            exclude_channels=self.config.roi_cutting.exclude_channels,
            use_markers=self.config.roi_cutting.use_markers,
            ignore_markers=self.config.roi_cutting.ignore_markers,
        )

    def yield_ready_channels(self) -> Iterator[tuple[str, str]]:
        """Yield all discovered local channels.

        Yields:
            Tuple of (channel_name, file_path).

        Raises:
            RuntimeError: If a expected local file is missing.
        """
        for channel, path in self.channel_map.items():

            # 2. Safety check: In local mode, files MUST exist
            if Path(path).exists():
                logger.info(f"Local file for {channel} verified: {path}")
                # 3. Yield as a tuple (channel, path)
                yield channel, path
            else:
                msg = f"Local error: Expected file for {channel} at {path} not found."
                logger.error(msg)
                # 4. Raise immediately to stop the controller
                raise RuntimeError(msg)

    def cleanup(self, path: Path) -> None:
        """No-op for local files (they are left untouched).

        Args:
            path: Path to the file (ignored).
        """
