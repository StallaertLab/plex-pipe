import pytest

import plex_pipe.io.filesystem as filesystem


def test_change_to_wsl_path():
    """
    Verifies valid Windows paths convert to /mnt/x/ format.
    """
    # Standard C drive
    assert filesystem.change_to_wsl_path(r"C:\Users\Data") == "/mnt/c/Users/Data"

    # Relative path (no drive)
    with pytest.raises(ValueError, match="Invalid Windows path"):
        filesystem.change_to_wsl_path(r"\Users\Data")

    # Invalid drive letter (symbol)
    with pytest.raises(ValueError, match="Invalid drive letter"):
        filesystem.change_to_wsl_path(r"1:\Users")
