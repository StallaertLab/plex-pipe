"""Image utilities for reading multiscale images and preparing RGB previews."""

import dask.array as da
import numpy as np
import zarr
from tifffile import TiffFile, imread


def get_org_im_shape(im_path):
    """
    Function to get the size of the original image.

    Args:
        im_path (str): Path to the image.
    Returns:
        tuple: The size of the image.
    """
    with TiffFile(im_path) as tif:

        width = tif.pages[0].imagewidth
        height = tif.pages[0].imagelength

    return (height, width)


def get_zarr_levels_num(path):
    """
    Get the number of multiscale levels in a Zarr file.

    Args:
        path (str): The path to the Zarr file.
    Returns:
        int: The number of multiscale levels.
    """
    store = imread(path, aszarr=True)
    group = zarr.open(store, mode="r")
    zattrs = group.attrs.asdict()

    return len(zattrs["multiscales"][0]["datasets"])


def get_all_resolutions(im_path):

    # Open the TIFF as a Zarr store (V3 compatible)
    with TiffFile(im_path) as tif:

        store = tif.aszarr()
        # Open the store - could be a Group or an Array
        z_obj = zarr.open(store, mode="r")

        # CASE 1: a single Array (Flat TIFF)
        if isinstance(z_obj, zarr.Array):
            im_list = [da.from_zarr(z_obj)]

        # CASE 2: a Group (Pyramidal TIFF)
        elif isinstance(z_obj, zarr.Group):
            # Find how many levels we actually have
            # Pyramidal TIFFs via tifffile usually have keys '0', '1', '2'...
            available_levels = len(tif.series[0].levels)

            im_list = []
            for level in range(available_levels):
                im_list.append(da.from_zarr(z_obj[str(level)]))

        else:
            raise TypeError(f"Unknown TIFF object type: {type(z_obj)}")

    return im_list


def get_small_image(im_path, req_level):
    """
    Function to get a set resolution level from a tiff file.
    If the file is flat, or the resolution level is not available it will be generated from the closest available level.

    Args:
        im_path (str): Path to the tiff file.
        req_level (int): Requested level of the image.
    Returns:
        np.array: The image of requested level.
    """
    # Open the TIFF as a Zarr store (V3 compatible)
    with TiffFile(im_path) as tif:

        store = tif.aszarr()
        # Open the store - could be a Group or an Array
        z_obj = zarr.open(store, mode="r")

        # CASE 1: a single Array (Flat TIFF)
        if isinstance(z_obj, zarr.Array):
            im = z_obj[:]
            level_loaded = 0

        # CASE 2: a Group (Pyramidal TIFF)
        elif isinstance(z_obj, zarr.Group):
            # Find how many levels we actually have
            # Pyramidal TIFFs via tifffile usually have keys '0', '1', '2'...
            available_levels = len(tif.series[0].levels)
            level_to_load = min(req_level, available_levels - 1)

            # Access the specific array within the group
            im = z_obj[str(level_to_load)][:]
            level_loaded = level_to_load

        else:
            raise TypeError(f"Unknown TIFF object type: {type(z_obj)}")

        # Final Step: downsample if necessary
        if req_level > level_loaded:
            # strided slicing for speed
            skip = 2 ** (req_level - level_loaded)
            im = im[..., ::skip, ::skip]

    return im


def prepare_rgb_image(im_path, int_min=None, int_max=None, req_level=0):
    """
    Function to change an image into RGB image of stretched intensity.

    Args:
        im_path (str): Path to the image.
        int_min (float): Lower intensity threshold for stretching.
        int_max (float): Upper intensity threshold for stretching.
    Returns:
        np.array: The RGB image.
    """

    # get the image of requested resolution
    im = get_small_image(im_path, req_level)

    # rescale between intensities
    if int_min is None:
        int_min = np.min(im)
    if int_max is None:
        int_max = np.max(im)

    im = (im - int_min) / (int_max - int_min)
    im = np.clip(im, 0, 1)

    im = (im * 255).astype(np.uint8)  # change to 8 bit

    # convert to RGB
    im_rgb = np.stack((im,) * 3, axis=-1)

    return im_rgb
