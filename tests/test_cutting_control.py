from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Import module under test
from plex_pipe.core_cutting.controller import (
    CorePreparationController as controller,
)
from plex_pipe.core_cutting.input_strategy import FileAvailabilityStrategy

# --- Fixtures ---


@pytest.fixture
def mock_metadata():
    """Creates a dummy metadata DataFrame with 2 cores."""
    return pd.DataFrame(
        {"roi_name": ["Core_01", "Core_02"], "geometry": ["poly1", "poly2"]}
    )


@pytest.fixture
def mock_image_paths():
    return {"DAPI": "/path/to/dapi.tif", "CD45": "/path/to/cd45.tif"}


@pytest.fixture
def mock_dependencies():
    """
    Mocks Cutter, Assembler, and File Strategy.
    """
    with (
        patch("plex_pipe.core_cutting.controller.CoreCutter") as MockCutter,
        patch("plex_pipe.core_cutting.controller.CoreAssembler") as MockAssembler,
        patch("plex_pipe.core_cutting.controller.read_ome_tiff") as mock_read,
        patch("plex_pipe.core_cutting.controller.write_temp_tiff") as mock_write,
        patch("plex_pipe.core_cutting.controller.os.makedirs"),
    ):

        # Setup specific mock behaviors
        mock_strategy = MagicMock(spec=FileAvailabilityStrategy)
        # Ensure channel_map is a dict so .keys() works during init
        mock_strategy.channel_map = {"DAPI": "path", "CD45": "path"}

        # Setup read_ome_tiff to return a mock array and a mock store (for closing)
        mock_store = MagicMock()
        mock_img = np.zeros((100, 100))
        mock_read.return_value = (mock_img, mock_store)

        yield {
            "Cutter": MockCutter,
            "Assembler": MockAssembler,
            "read_ome_tiff": mock_read,
            "store": mock_store,
            "write_temp_tiff": mock_write,
            "strategy": mock_strategy,
        }


@pytest.fixture
def test_controller(mock_metadata, mock_image_paths, mock_dependencies):
    """Instantiates the controller with mocked dependencies."""
    return controller(
        metadata_df=mock_metadata,
        temp_dir="/tmp/cores",
        output_dir="/tmp/output",
        file_strategy=mock_dependencies["strategy"],
    )


# --- Tests for Cutting Logic ---


def test_cut_channel_logic(test_controller, mock_dependencies, mock_metadata):
    """
    Verifies that cutting a channel iterates through metadata,
    extracts cores, and writes temp files.
    """
    # Action
    test_controller.cut_channel("DAPI", "/path/to/dapi.tif")

    # 1. Verify Image Loading
    mock_dependencies["read_ome_tiff"].assert_called_with("/path/to/dapi.tif")

    # 2. Verify Cutting (called once per core)
    cutter_instance = test_controller.cutter
    assert cutter_instance.extract_core.call_count == len(mock_metadata)

    # 3. Verify Writing
    assert mock_dependencies["write_temp_tiff"].call_count == len(mock_metadata)


def test_cut_channel_resource_safety(test_controller, mock_dependencies):
    """
    Ensures file handles are closed even if cutting crashes.
    """
    # Simulate a crash during core extraction
    test_controller.cutter.extract_core.side_effect = RuntimeError("Cutting failed!")

    with pytest.raises(RuntimeError):
        test_controller.cut_channel("DAPI", "bad_file.tif")

    # The store.close() must still be called
    mock_dependencies["store"].close.assert_called_once()


# --- Tests for the Main Run Loop (Integration) ---


def test_run_loop_workflow(test_controller, mock_dependencies):
    """
    Simulates a full run where files appear sequentially.
    """
    strategy = mock_dependencies["strategy"]

    # Mock yield_ready_channels to return items
    strategy.yield_ready_channels.return_value = [
        ("DAPI", "/path/to/dapi.tif"),
        ("CD45", "/path/to/cd45.tif"),
    ]

    # Run the controller
    test_controller.run(poll_interval=0.01)

    # Assertions

    # 1. Check Cutting Order
    # cut_channel should be called twice (DAPI, then CD45)
    assert mock_dependencies["read_ome_tiff"].call_count == 2

    # 2. Check Cleanup
    # strategy.cleanup should be called for each path
    assert strategy.cleanup.call_count == 2

    # 3. Check Assembly
    # Should happen after all channels are processed
    # Iterates over metadata (2 cores)
    assert test_controller.assembler.assemble_core.call_count == 2

    # 4. Check Completed Set
    assert test_controller.completed_channels == ["DAPI", "CD45"]


def test_run_loop_cleanup_trigger(test_controller, mock_dependencies):
    """
    Verifies that the file strategy's cleanup method is called immediately
    after cutting a channel.
    """
    strategy = mock_dependencies["strategy"]
    strategy.yield_ready_channels.return_value = [("DAPI", "/path/to/dapi.tif")]

    test_controller.run(poll_interval=0)

    # Verify cleanup called
    assert strategy.cleanup.call_count == 1
