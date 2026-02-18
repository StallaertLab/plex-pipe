import pytest

import plex_pipe.utils.file_utils as file_utils


def test_change_to_wsl_path():
    """
    Verifies valid Windows paths convert to /mnt/x/ format.
    """
    # Standard C drive
    assert file_utils.change_to_wsl_path(r"C:\Users\Data") == "/mnt/c/Users/Data"

    # Relative path (no drive)
    with pytest.raises(ValueError, match="Invalid Windows path"):
        file_utils.change_to_wsl_path(r"\Users\Data")

    # Invalid drive letter (symbol)
    with pytest.raises(ValueError, match="Invalid drive letter"):
        file_utils.change_to_wsl_path(r"1:\Users")
