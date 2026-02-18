import os
import sys
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch

import pytest

from plex_pipe.utils.globus_utils import (
    GlobusConfig,
    GlobusEndpoint,
    list_globus_tifs,
)

# --- 1. Testing GlobusEndpoint Path Logic ---


def test_endpoint_init_posix_default():
    """Test that Linux/Mac defaults to Home directory."""
    with patch("os.name", "posix"):
        with patch.object(Path, "home") as mock_home:
            mock_home.return_value.resolve.return_value = PurePosixPath("/home/user")
            endpoint = GlobusEndpoint("id-123")
            assert endpoint.mode == "rooted"
            assert endpoint.shared_root == PurePosixPath("/home/user")


def test_endpoint_init_windows_default():
    """Test that Windows defaults to multi_drive."""
    with patch("os.name", "nt"):
        endpoint = GlobusEndpoint("id-123")
        assert endpoint.mode == "multi_drive"
        assert endpoint.shared_root is None


@pytest.mark.skipif(
    sys.platform != "win32", reason="Requires Windows drive letter logic"
)
def test_local_to_globus_windows_multi_drive():
    """Test C:\\Data -> /C/Data on Windows."""
    with patch("os.name", "nt"):
        endpoint = GlobusEndpoint("id-123", root=None)
        # Mock resolve to return the path as is for testing
        with patch.object(
            Path, "resolve", side_effect=lambda self: self, autospec=True
        ):
            local = "C:/Data/image.tif"
            result = endpoint.local_to_globus(local)
            assert result == "/C/Data/image.tif"


def test_local_to_globus_rooted_scope_error():
    """Test that accessing paths outside root raises ValueError."""
    endpoint = GlobusEndpoint("id-123", root="/data/shared")
    with patch.object(Path, "resolve", side_effect=lambda self: self, autospec=True):
        with pytest.raises(ValueError, match="outside Globus scope"):
            endpoint.local_to_globus("/home/user/private.tif")


@pytest.mark.skipif(
    sys.platform != "win32", reason="Requires Windows drive letter logic"
)
def test_globus_to_local_windows_multi():
    """Test /D/Temp -> D:\\Temp conversion."""
    with patch("os.name", "nt"):
        endpoint = GlobusEndpoint("id-123", root=None)
        result = endpoint.globus_to_local("/D/Temp/file.txt")
        # Check parts to avoid slash direction issues in assertions
        assert str(result).endswith("Temp\\file.txt")
        assert result.drive == "D:"


# --- 2. Testing GlobusConfig Registry ---


@pytest.fixture
def mock_yaml_config():
    return {
        "gc": {
            "client_id": "client-abc",
            "collections": {
                "source_lab": {"id": "src-uuid", "root": "/remote/data"},
                "dest_workstation": {"id": "dest-uuid", "root": None},
            },
        },
        "transfer_tokens": {
            "access_token": "at",
            "refresh_token": "rt",
            "expires_at_seconds": 123,
        },
    }


def test_globus_config_init(mock_yaml_config):
    config = GlobusConfig(mock_yaml_config, "source_lab", "dest_workstation")
    assert config.source.collection_id == "src-uuid"
    assert config.destination.mode == ("multi_drive" if os.name == "nt" else "rooted")


def test_globus_config_missing_key(mock_yaml_config):
    with pytest.raises(KeyError):
        GlobusConfig(mock_yaml_config, "wrong_key", "dest_workstation")


# --- 3. Testing Globus SDK Integration (Mocked) ---


@patch("plex_pipe.utils.globus_utils.create_globus_tc")
def test_list_globus_tifs(mock_create_tc, mock_yaml_config):
    # Setup Mock TransferClient
    mock_tc = MagicMock()
    mock_create_tc.return_value = mock_tc

    # Simulate a Globus directory listing response
    mock_tc.operation_ls.return_value = [
        {"name": "image1.tif", "type": "file"},
        {"name": "notes.txt", "type": "file"},
        {"name": "subfolder", "type": "dir"},
    ]

    gc = GlobusConfig(mock_yaml_config, "source_lab", "dest_workstation")
    results = list_globus_tifs(gc, "/remote/data")

    assert len(results) == 1
    assert results[0] == "/remote/data/image1.tif"
    mock_tc.operation_ls.assert_called_once()
