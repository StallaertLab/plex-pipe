"""Napari viewer helpers for displaying and saving ROI layers."""

from pathlib import Path
from typing import Any

import napari
from qtpy.QtWidgets import QFileDialog

from plex_pipe.stages.roi_definition.roi_utils import (
    get_visual_rectangles,
    prepare_poly_df_for_saving,
    read_in_saved_rois,
)


def redo_cores_layer(
    viewer: napari.Viewer,
    data: list[Any] | None = None,
    edge_width: int = 2,
    shape_type: str | list[str] = "polygon",
) -> None:
    """Creates or replaces the ``ROIs`` layer in a viewer.

    Args:
        viewer: Viewer instance to update.
        data: Vertices describing the shapes. Defaults to None.
        edge_width: Width of the shape edges. Defaults to 2.
        shape_type: Napari shape type(s). Defaults to "polygon".
    """
    if "ROIs" in viewer.layers:
        viewer.layers.remove("ROIs")

    # initialize data if None
    if data is None:
        data = []

    viewer.add_shapes(
        data,
        shape_type=shape_type,
        edge_color="green",
        face_color="transparent",
        edge_width=edge_width,
        name="ROIs",
    )


def redo_bbox_layer(
    viewer: napari.Viewer,
    data: list[list[float]] | None = None,
    text: list[str] | None = None,
    edge_width: int = 2,
) -> None:
    """Creates or replaces the ``bounding_boxes`` layer in a viewer.

    Args:
        viewer: Viewer instance to update.
        data: Rectangle coordinates. Defaults to None.
        text: Labels shown next to rectangles. Defaults to None.
        edge_width: Width of the shape edges. Defaults to 2.
    """
    if "bounding_boxes" in viewer.layers:
        viewer.layers.remove("bounding_boxes")

    # initialize data if None
    if data is None:
        data = []

    viewer.add_shapes(
        data,
        shape_type="rectangle",
        edge_color="yellow",
        face_color="transparent",
        edge_width=edge_width,
        name="bounding_boxes",
        text={
            "string": text,
            "size": 20,
            "color": "yellow",
            "anchor": "upper_left",
        },
    )
    viewer.layers["bounding_boxes"].editable = False


def display_saved_rois(
    viewer: napari.Viewer,
    IM_LEVEL: int,
    save_path: Path,
    edge_width: int = 2,
) -> None:
    """Loads ROI annotations from disk and shows them in the viewer.

    Args:
        viewer: Viewer instance where layers are added.
        IM_LEVEL: Image pyramid level used when the ROIs were saved.
        edge_width: Width of the shape edges. Defaults to 2.
        save_path: File path of the saved ROIs. Defaults to None.
    """
    rect_list, poly_list, df = read_in_saved_rois(save_path, IM_LEVEL=IM_LEVEL)

    if df is not None:
        roi_names = df["roi_name"].tolist()
        shape_types = df.poly_type.to_list()
    else:
        roi_names = []
        shape_types = []
        viewer.status = "No previous rois found. Displaying empty layers."

    redo_bbox_layer(viewer, rect_list, edge_width=edge_width, text=roi_names)
    redo_cores_layer(viewer, poly_list, edge_width=edge_width, shape_type=shape_types)


def save_rois_from_viewer(
    viewer: napari.Viewer,
    org_im_shape: tuple[int, int],
    req_level: int,
    save_path: str | Path | None = None,
) -> None:
    """Saves ROIs drawn in the viewer to disk and updates the displayed layers.

    Args:
        viewer: Viewer containing a ``ROIs`` shapes layer.
        org_im_shape: Shape of the original image (height, width).
        req_level: Resolution level at which the ROIs are defined.
        save_path: Destination file path. Defaults to None.
    """
    if "ROIs" in viewer.layers:

        # get the saving path if not provided
        if save_path is None:
            # open dialog for getting a dir to save pkl file
            save_path = QFileDialog.getSaveFileName(filter="Pickle file (*.pkl)")[0]

        # wrap
        save_path = Path(save_path)

        # get the polygon data
        poly_data = viewer.layers["ROIs"].data
        poly_types = viewer.layers["ROIs"].shape_type

        # prepare df for saving
        df = prepare_poly_df_for_saving(poly_data, poly_types, req_level, org_im_shape)

        # save the rois
        df.to_pickle(save_path.with_suffix(".pkl"))
        df.to_csv(save_path.with_suffix(".csv"), index=False)

        # prepare the cores visual for saving
        rect_list = get_visual_rectangles(df, req_level)
        poly_list = [
            (x / (2 ** (req_level))).astype("int")
            for x in df.polygon_vertices.to_list()
        ]

        # change the visualization
        redo_bbox_layer(viewer, rect_list, df["roi_name"].tolist())
        redo_cores_layer(viewer, poly_list, shape_type=df.poly_type.to_list())

        # get a screenshot of the viewer
        screenshot_path = save_path.with_suffix(".png")
        # reset zoom
        viewer.reset_view()
        viewer.screenshot(screenshot_path, canvas_only=True)

        viewer.status = f"ROIs saved to {save_path}"

        viewer.layers.selection.add(viewer.layers["ROIs"])

    else:
        viewer.status = 'No layer called "ROIs" found!'
