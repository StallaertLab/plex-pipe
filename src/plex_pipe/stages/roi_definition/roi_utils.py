"""ROI processing helpers for filtering, resizing and saving polygons."""

import os
import pickle as pkl
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import Polygon


def pre_select_objects(
    masks: list[dict[str, Any]],
    im: np.ndarray,
    min_area: int,
    max_area: int,
    min_iou: float,
    min_stability: float,
    min_int: float,
) -> list[dict[str, Any]]:
    """Filter objects based on area, IoU, stability, and intensity.

    Args:
        masks: List of mask dictionaries.
        im: Source image array.
        min_area: Minimum area threshold.
        max_area: Maximum area threshold.
        min_iou: Minimum predicted IoU threshold.
        min_stability: Minimum stability score threshold.
        min_int: Minimum mean intensity threshold.

    Returns:
        List of filtered mask dictionaries.
    """
    masks_filtered = []

    for item in masks:

        bbox_area = item["bbox"][2] * item["bbox"][3]

        if (
            (bbox_area > min_area)
            and (bbox_area < max_area)
            and (item["predicted_iou"] > min_iou)
            and (item["stability_score"] > min_stability)
        ):

            rect = xywh_to_corners(item["bbox"]).astype(int)

            crop_slice = (slice(rect[0, 0], rect[2, 0]), slice(rect[0, 1], rect[1, 1]))
            im_crop = im[crop_slice]
            mask_crop = item["segmentation"][crop_slice]

            mean_int = np.average(im_crop, weights=mask_crop)

            if mean_int > min_int:
                masks_filtered.append(item)

    return masks_filtered


def do_boxes_overlap(
    bbox1: list[int] | tuple[int, ...], bbox2: list[int] | tuple[int, ...]
) -> bool:
    """Check if two bounding boxes overlap.

    Args:
        bbox1: The first bounding box (x, y, w, h).
        bbox2: The second bounding box (x, y, w, h).

    Returns:
        True if the bounding boxes overlap, False otherwise.
    """
    x1_min, y1_min, w1, h1 = bbox1
    x2_min, y2_min, w2, h2 = bbox2

    x1_max, y1_max = x1_min + w1, y1_min + h1
    x2_max, y2_max = x2_min + w2, y2_min + h2

    # Check for no overlap
    return not (
        x1_max <= x2_min or x2_max <= x1_min or y1_max <= y2_min or y2_max <= y1_min
    )


def remove_overlapping_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove overlapping objects, keeping those with higher predicted IoU.

    Args:
        objects: List of object dictionaries containing 'bbox' and 'predicted_iou'.

    Returns:
        Filtered list of objects.
    """
    objects = sorted(
        objects, key=lambda x: x["predicted_iou"], reverse=True
    )  # Sort by iou descending
    remaining_objects = []

    while objects:
        current = objects.pop(0)
        remaining_objects.append(current)
        # Remove objects that overlap with the current one
        objects = [
            obj for obj in objects if not do_boxes_overlap(current["bbox"], obj["bbox"])
        ]

    return remaining_objects


def xywh_to_corners(xywh: list[int] | np.ndarray) -> np.ndarray:
    """Convert (x, y, w, h) format to corner coordinates.

    Args:
        xywh: Bounding box in (x, y, w, h) format.

    Returns:
        Array of shape (4, 2) containing corner coordinates [row, col].
    """
    x, y, w, h = xywh
    return np.array(
        [
            [y, x],  # Top-left (swap x and y)
            [y, x + w],  # Top-right (swap x and y)
            [y + h, x + w],  # Bottom-right (swap x and y)
            [y + h, x],  # Bottom-left (swap x and y)
        ]
    )


def get_refined_rectangles(
    masks: list[dict[str, Any]],
    im: np.ndarray,
    min_area: int,
    max_area: int,
    min_iou: float,
    min_stability: float,
    min_int: float,
) -> list[np.ndarray]:
    """Select and refine object rectangles based on quality metrics.

    Filters objects by area, IoU, stability, and intensity, then performs
    non-maximum suppression to remove overlaps.

    Args:
        masks: List of mask dictionaries.
        im: Source image array.
        min_area: Minimum area threshold.
        max_area: Maximum area threshold.
        min_iou: Minimum IoU threshold.
        min_stability: Minimum stability score threshold.
        min_int: Minimum intensity threshold.

    Returns:
        List of corner coordinate arrays for the refined rectangles.
    """
    masks_pre_selected = pre_select_objects(
        masks, im, min_area, max_area, min_iou, min_stability, min_int
    )

    masks_non_overlapping = remove_overlapping_objects(masks_pre_selected)

    rect_list = [xywh_to_corners(mask["bbox"]) for mask in masks_non_overlapping]

    return rect_list


def create_bbox(polygon: np.ndarray) -> list[int]:
    """Create a bounding box from polygon vertices.

    Args:
        polygon: Array of (x, y) points.

    Returns:
        Bounding box as [x_min, x_max, y_min, y_max].
    """
    x_min = int(np.min(polygon[:, 0]))
    x_max = int(np.max(polygon[:, 0]))
    y_min = int(np.min(polygon[:, 1]))
    y_max = int(np.max(polygon[:, 1]))

    return [x_min, x_max, y_min, y_max]


def prepare_polygons(
    poly_data: list[Any], req_level: int, org_im_shape: tuple[int, int]
) -> list[np.ndarray | None]:
    """Rescale polygons to original size and clip to image boundaries.

    Args:
        poly_data: List of polygons (lists of vertices).
        req_level: Resolution level used for the polygon definition.
        org_im_shape: Shape of the original image (height, width).

    Returns:
        List of rescaled and trimmed polygons (as arrays), or None if empty.
    """
    # get vertices for the original image
    frame_vertices = xywh_to_corners([0, 0, org_im_shape[1], org_im_shape[0]])
    frame = Polygon(frame_vertices)

    trim_poly_list = []
    for polygon_vertices in poly_data:

        # rescale the polygons to the original image size
        polygon_vertices = np.array(polygon_vertices).astype(int) * (2**req_level)

        polygon = Polygon(polygon_vertices)

        # Compute the intersection
        intersection = polygon.intersection(frame)

        # add the polygon to the list
        if not intersection.is_empty:
            trim_poly_list.append(np.array(intersection.exterior.coords)[:-1, :])
        else:
            trim_poly_list.append(None)

    return trim_poly_list


def sort_cores(df: pd.DataFrame) -> pd.DataFrame:
    """Sort cores in the DataFrame based on spatial position (row, then column).

    Args:
        df: DataFrame containing 'row_start' and 'column_start'.

    Returns:
        Sorted DataFrame.
    """
    # Round the columns and sort
    df = (
        df.assign(
            row_rounded=lambda x: np.around(x["row_start"] / 2, decimals=-3),
            col_rounded=lambda x: np.around(x["column_start"] / 2, decimals=-3),
        )
        .sort_values(by=["row_rounded", "col_rounded"])
        .reset_index(drop=True)
    )

    # Drop the temporary columns if not needed
    df = df.drop(columns=["row_rounded", "col_rounded"])

    return df


def prepare_poly_df_for_saving(
    poly_data: list[Any],
    poly_types: list[str],
    req_level: int,
    org_im_shape: tuple[int, int],
) -> pd.DataFrame:
    """Create a DataFrame of polygons ready for saving.

    Args:
        poly_data: List of polygon vertex data.
        poly_types: List of polygon type strings.
        req_level: Resolution level used for definition.
        org_im_shape: Original image dimensions.

    Returns:
        DataFrame containing ROI metadata and geometries.
    """
    # initialize the dataframe
    df = pd.DataFrame(
        columns=[
            "roi_name",
            "row_start",
            "row_stop",
            "column_start",
            "column_stop",
            "poly_type",
            "polygon_vertices",
        ]
    ).astype(
        {
            "roi_name": "str",
            "row_start": "int",
            "row_stop": "int",
            "column_start": "int",
            "column_stop": "int",
            "poly_type": "str",
            "polygon_vertices": "object",
        }
    )

    # populate polygon info
    df["poly_type"] = poly_types

    # populate polygon vertices
    trim_poly_list = prepare_polygons(poly_data, req_level, org_im_shape)
    df["polygon_vertices"] = trim_poly_list

    # drop None polygons
    df = df.dropna(subset=["polygon_vertices"])

    # create the array of bounding boxes
    bbox_array = np.array([create_bbox(poly) for poly in df.polygon_vertices.to_list()])

    df.loc[:, ["row_start", "row_stop", "column_start", "column_stop"]] = bbox_array

    # arrange polygons
    df = sort_cores(df)

    # add core names
    df["roi_name"] = [f"ROI_{str(i).zfill(3)}" for i in range(len(df))]

    return df


def get_visual_rectangles(df: pd.DataFrame, req_level: int) -> list[np.ndarray]:
    """Extract rectangle boundaries from DataFrame adjusted for resolution.

    Args:
        df: DataFrame containing ROI metadata.
        req_level: Requested resolution level for display.

    Returns:
        List of rectangle corner arrays.
    """
    rect_list = df.apply(
        lambda x: xywh_to_corners(
            [
                x["column_start"],
                x["row_start"],
                x["column_stop"] - x["column_start"],
                x["row_stop"] - x["row_start"],
            ]
        ),
        axis=1,
    ).tolist()
    rect_list = [(x / (2 ** (req_level))).astype("int") for x in rect_list]

    return rect_list


def read_in_saved_rois(
    save_path: Path, IM_LEVEL: int
) -> tuple[list[np.ndarray], list[np.ndarray], pd.DataFrame | None]:
    """Load saved ROIs from disk.

    Args:
        save_path: Path to the saved ROI file.
        IM_LEVEL: Image resolution level for scaling coordinates.

    Returns:
        Tuple containing list of rectangles, list of polygons, and the metadata DataFrame.
    """
    if os.path.exists(save_path.with_suffix(".pkl")):
        with open(save_path.with_suffix(".pkl"), "rb") as f:
            df = pkl.load(f)
        rect_list = get_visual_rectangles(df, IM_LEVEL)
        poly_list = [
            (x / (2**IM_LEVEL)).astype("int") for x in df.polygon_vertices.to_list()
        ]
        return rect_list, poly_list, df
    else:
        return [], [], None
