import os
from pathlib import Path
from typing import Any

import dask.array as da
import zarr
from tifffile import TiffFile, imwrite


def change_to_wsl_path(path):
    """
    Converts a Windows path to a WSL path and checks if the drive is mounted.

    Args:
        path (str): The Windows path to convert.

    Returns:
        str: The WSL path if the drive is mounted, or an error message if not.
    """
    if ":" not in path:
        raise ValueError(
            "Invalid Windows path. Ensure the path includes a drive letter (e.g., C:\\)."
        )

    drive_letter = path[0].lower()
    if not ("a" <= drive_letter <= "z"):
        raise ValueError(f"Invalid drive letter: '{drive_letter}' in path '{path}'.")

    # Convert to WSL path
    wsl_path = f"/mnt/{drive_letter}" + path[2:].replace("\\", "/")

    return wsl_path


def write_temp_tiff(array, core_id: str, channel: str, temp_dir: str):
    """Save an array as ``temp/<core_id>/<channel>.tiff``.

    Args:
        array (numpy.ndarray): Image data to save.
        core_id (str): Core identifier.
        channel (str): Channel name.
        temp_dir (str): Base directory for temporary files.
    """
    core_path = os.path.join(temp_dir, core_id)
    os.makedirs(core_path, exist_ok=True)
    fname = os.path.join(core_path, f"{channel}.tiff")
    imwrite(fname, array)


def read_ome_tiff(path: str, level_num: int = 0) -> tuple[da.Array, Any]:
    """Load an OME-TIFF (flat or pyramidal) as a Dask array.

    Args:
        path (str): Path to the TIFF file.
        level_num (int, optional): Multiscale level to read. Defaults to 0 (highest res).

    Returns:
        tuple[da.Array, Any]: The image array and the underlying store.
    """
    with TiffFile(path) as tif:

        store = tif.aszarr()
        # Open the store - could be a Group or an Array
        z_obj = zarr.open(store, mode="r")

        # CASE 1: a single Array (Flat TIFF)
        if isinstance(z_obj, zarr.Array):
            im_da = da.from_zarr(z_obj)

        # CASE 2: a Group (Pyramidal TIFF)
        elif isinstance(z_obj, zarr.Group):
            # Access the specific array within the group
            im_da = da.from_zarr(z_obj[str(level_num)])

    return im_da, store


def list_local_files(image_dir: str | Path) -> list[str]:
    """List ``*.tif*`` files within a directory.

    Args:
        image_dir (str | Path): Directory to search.

    Returns:
        list[str]: Sorted list of matching file paths.
    """
    image_dir = Path(image_dir)  # Ensures uniform behavior
    return [str(p) for p in image_dir.glob("*.tif*")]
