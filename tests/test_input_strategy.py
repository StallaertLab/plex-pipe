from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from globus_sdk import GlobusAPIError

from plex_pipe.core_cutting.input_strategy import (
    GlobusFileStrategy,
    LocalFileStrategy,
)

# --- Fixtures ---


@pytest.fixture
def mock_config():
    """Mocks the configuration object passed to strategies."""
    cfg = MagicMock()
    cfg.general.image_dir = "/data/images"
    cfg.roi_cutting.include_channels = None
    cfg.roi_cutting.exclude_channels = None
    cfg.roi_cutting.use_markers = None
    cfg.roi_cutting.ignore_markers = None
    cfg.temp_dir = Path("/tmp/plex_pipe")
    return cfg


@pytest.fixture
def mock_discover_channels():
    with patch("plex_pipe.core_cutting.input_strategy.discover_channels") as mock:
        yield mock


@pytest.fixture
def mock_globus_utils():
    with (
        patch("plex_pipe.core_cutting.input_strategy.create_globus_tc") as mock_tc,
        patch("plex_pipe.core_cutting.input_strategy.GlobusConfig") as mock_gc_cls,
    ):
        yield mock_tc, mock_gc_cls


# --- LocalFileStrategy Tests ---


def test_local_strategy_init(mock_config, mock_discover_channels):
    """Verifies initialization and channel discovery."""
    mock_discover_channels.return_value = {"DAPI": "/data/images/dapi.tif"}

    strategy = LocalFileStrategy(mock_config)

    assert strategy.channel_map == {"DAPI": "/data/images/dapi.tif"}
    mock_discover_channels.assert_called_once()


def test_local_strategy_yield_success(mock_config, mock_discover_channels):
    """Verifies yielding of existing local files."""
    mock_discover_channels.return_value = {"DAPI": "/data/images/dapi.tif"}
    strategy = LocalFileStrategy(mock_config)

    with patch.object(Path, "exists", return_value=True):
        results = list(strategy.yield_ready_channels())

    assert len(results) == 1
    assert results[0] == ("DAPI", "/data/images/dapi.tif")


def test_local_strategy_yield_missing_file(mock_config, mock_discover_channels):
    """Verifies error when local file is missing."""
    mock_discover_channels.return_value = {"DAPI": "/data/images/missing.tif"}
    strategy = LocalFileStrategy(mock_config)

    with patch.object(Path, "exists", return_value=False):
        with pytest.raises(RuntimeError, match="not found"):
            list(strategy.yield_ready_channels())


def test_local_strategy_cleanup(mock_config, mock_discover_channels):
    """Verifies cleanup does nothing for local strategy."""
    mock_discover_channels.return_value = {}
    strategy = LocalFileStrategy(mock_config)

    # Should not raise error or delete anything
    with patch.object(Path, "unlink") as mock_unlink:
        strategy.cleanup(Path("/some/path"))
        mock_unlink.assert_not_called()


# --- GlobusFileStrategy Tests ---


@pytest.fixture
def mock_gc():
    """Creates a mock GlobusConfig with source/dest endpoints."""
    gc = MagicMock()
    gc.client_id = "client-id"
    gc.transfer_tokens = {
        "refresh_token": "dummy_rt",
        "access_token": "dummy_at",
        "expires_at_seconds": 3600,
    }
    gc.source.collection_id = "source-uuid"
    gc.destination.collection_id = "dest-uuid"

    # Mock path translation
    # remote path -> local relative path for transfer map
    gc.destination.local_to_globus.side_effect = lambda p: f"/dest/{p.name}"
    gc.destination.globus_to_local.side_effect = lambda p: Path(
        f"/local/{Path(p).name}"
    )

    return gc


def test_globus_strategy_init_and_map(
    mock_config, mock_discover_channels, mock_globus_utils, mock_gc
):
    """Verifies initialization and transfer map construction."""
    mock_create_tc, _ = mock_globus_utils

    # Setup discovery
    mock_discover_channels.return_value = {
        "DAPI": "/remote/source/dapi.tif",
        "CD45": "/remote/source/cd45.tif",
    }

    strategy = GlobusFileStrategy(mock_config, mock_gc)

    # Check Transfer Client creation
    mock_create_tc.assert_called_with("client-id", mock_gc.transfer_tokens)

    # Check Transfer Map
    assert "DAPI" in strategy.transfer_map
    remote, dest_globus = strategy.transfer_map["DAPI"]
    assert remote == "/remote/source/dapi.tif"
    assert dest_globus == "/dest/dapi.tif"


def test_globus_strategy_yield(
    mock_config, mock_discover_channels, mock_globus_utils, mock_gc
):
    """Verifies polling and yielding of transferred files."""
    mock_create_tc, _ = mock_globus_utils
    mock_tc = mock_create_tc.return_value

    # Setup
    mock_discover_channels.return_value = {"DAPI": "/remote/dapi.tif"}
    strategy = GlobusFileStrategy(mock_config, mock_gc)

    # Manually set pending task
    strategy.pending_tasks = ["task-1"]

    # Mock successful transfer response
    mock_tc.task_successful_transfers.return_value = [
        {"source_path": "/remote/dapi.tif"}
    ]

    # Patch sleep to avoid waiting
    with patch("time.sleep"):
        gen = strategy.yield_ready_channels()
        channel, local_path = next(gen)

    assert channel == "DAPI"
    # globus_to_local mock returns /local/dapi.tif
    assert str(local_path) == str(Path("/local/dapi.tif"))

    # Ensure loop finishes (StopIteration)
    with pytest.raises(StopIteration):
        next(gen)


def test_globus_strategy_submit_batch(
    mock_config, mock_discover_channels, mock_globus_utils, mock_gc
):
    """Verifies batch submission logic."""
    mock_create_tc, _ = mock_globus_utils
    mock_tc = mock_create_tc.return_value

    # Setup discovery with 3 channels
    mock_discover_channels.return_value = {
        "C1": "/r/c1.tif",
        "C2": "/r/c2.tif",
        "C3": "/r/c3.tif",
    }

    strategy = GlobusFileStrategy(mock_config, mock_gc)

    # Mock submit_transfer to return a task id
    mock_tc.submit_transfer.side_effect = [{"task_id": "t1"}, {"task_id": "t2"}]

    # Run with batch_size=2
    strategy.submit_all_transfers(batch_size=2)

    # Should have called submit_transfer twice (3 items, batch 2 -> 2 batches)
    assert mock_tc.submit_transfer.call_count == 2
    assert strategy.pending_tasks == ["t1", "t2"]


def test_globus_strategy_cleanup_enabled(
    mock_config, mock_gc, mock_globus_utils, mock_discover_channels
):
    """Verifies cleanup removes file when enabled."""
    strategy = GlobusFileStrategy(mock_config, mock_gc, cleanup_enabled=True)
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True

    strategy.cleanup(mock_path)
    mock_path.unlink.assert_called_once()


def test_globus_strategy_cleanup_disabled(
    mock_config, mock_gc, mock_globus_utils, mock_discover_channels
):
    """Verifies cleanup skips removal when disabled."""
    strategy = GlobusFileStrategy(mock_config, mock_gc, cleanup_enabled=False)
    mock_path = MagicMock(spec=Path)

    strategy.cleanup(mock_path)
    mock_path.unlink.assert_not_called()


def test_globus_strategy_yield_api_error(
    mock_config, mock_discover_channels, mock_globus_utils, mock_gc
):
    """Verifies handling of GlobusAPIError during polling."""
    mock_create_tc, _ = mock_globus_utils
    mock_tc = mock_create_tc.return_value

    # Setup
    mock_discover_channels.return_value = {"DAPI": "/remote/dapi.tif"}
    strategy = GlobusFileStrategy(mock_config, mock_gc)
    strategy.pending_tasks = ["task-1"]

    class FakeGlobusAPIError(GlobusAPIError):
        def __init__(self, http_status, message):
            self.http_status = http_status
            self._message = message

        @property
        def message(self):
            return self._message

    # Mock API Errors
    # 1. Progress error (should be ignored/retried)
    mock_err_progress = FakeGlobusAPIError(400, "Task is still in progress")

    # 2. Fatal error (should be raised)
    mock_err_fatal = FakeGlobusAPIError(500, "Fatal error")

    mock_tc.task_successful_transfers.side_effect = [mock_err_progress, mock_err_fatal]

    with patch("time.sleep"):  # Skip sleep
        with pytest.raises(GlobusAPIError) as excinfo:
            next(strategy.yield_ready_channels())

    assert excinfo.value == mock_err_fatal
    assert mock_tc.task_successful_transfers.call_count == 2
