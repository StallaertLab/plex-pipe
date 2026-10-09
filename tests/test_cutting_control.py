from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Import module under test
from plex_pipe.stages.roi_preparation.controller import (
    RoiPreparationController as controller,
)
from plex_pipe.stages.roi_preparation.file_strategy import (
    FileAvailabilityStrategy,
)

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
        patch("plex_pipe.stages.roi_preparation.controller.CoreCutter") as MockCutter,
        patch(
            "plex_pipe.stages.roi_preparation.controller.CoreAssembler"
        ) as MockAssembler,
        patch("plex_pipe.stages.roi_preparation.controller.os.makedirs"),
    ):

        # Setup specific mock behaviors
        mock_strategy = MagicMock(spec=FileAvailabilityStrategy)
        # Ensure channel_map is a dict so .keys() works during init
        mock_strategy.channel_map = {"DAPI": "path", "CD45": "path"}

        yield {
            "Cutter": MockCutter,
            "Assembler": MockAssembler,
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
    test_controller.run()

    # Assertions

    # 1. Check Cutting Order
    # The cutter cuts each channel once, in the order they arrive
    cut_calls = test_controller.cutter.cut_image.call_args_list
    assert [c.args[:2] for c in cut_calls] == [
        ("/path/to/dapi.tif", "DAPI"),
        ("/path/to/cd45.tif", "CD45"),
    ]
    assert cut_calls[0].args[3] == "/tmp/cores"

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

    test_controller.run()

    # Verify cleanup called
    assert strategy.cleanup.call_count == 1
