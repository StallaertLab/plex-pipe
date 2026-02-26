from unittest.mock import patch

import numpy as np
import pytest

# Import module under test
import plex_pipe.image.utils as utils

# --- Fixtures ---


@pytest.fixture
def mock_zarr_structure():
    """
    Creates a mock Zarr/OME-Zarr metadata structure.
    """
    return {
        "multiscales": [
            {
                "datasets": [
                    {"path": "0"},  # Level 0 (Full res)
                    {"path": "1"},  # Level 1
                    {"path": "2"},  # Level 2
                ]
            }
        ]
    }


@patch("plex_pipe.image.utils.get_small_image")
def test_prepare_rgb_image_math(mock_get_small):
    """
    Verifies the math of contrast stretching and RGB conversion.
    This ensures images aren't just black or white.
    """
    # Create a gradient image 0..100
    # Reshape to 10x10
    input_im = np.arange(100).reshape(10, 10)
    mock_get_small.return_value = input_im

    # Request normalization with explicit intensity limits
    # Pixels < 10 become 0, Pixels > 90 become 255.
    rgb = utils.prepare_rgb_image("dummy", int_min=10, int_max=90)

    # 1. Check Output Shape: Must be (H, W, 3)
    assert rgb.shape == (10, 10, 3)

    # 2. Check Data Type: Must be uint8 for plotting/saving
    assert rgb.dtype == np.uint8

    # 3. Check Clipping (Low End)
    # Input 0 should be clipped to 0
    assert np.all(rgb[0, 0] == [0, 0, 0])

    # 4. Check Clipping (High End)
    # Input 99 should be clipped to 255
    assert np.all(rgb[9, 9] == [255, 255, 255])

    # 5. Check Mid tones (Logic check)
    # Value 50 should be roughly middle gray (~127)
    # (50 - 10) / (90 - 10) = 40/80 = 0.5 -> 127.5
    mid_pixel = rgb[5, 0]  # Input value 50
    assert 120 < mid_pixel[0] < 135
