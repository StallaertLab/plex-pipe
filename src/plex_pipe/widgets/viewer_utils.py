"""Napari viewer helpers for displaying and saving ROI layers."""

from pathlib import Path

import napari
from qtpy.QtWidgets import QFileDialog

from plex_pipe.core_definition.roi_utils import (
    get_visual_rectangles,
    prepare_poly_df_for_saving,
    read_in_saved_rois,
)


def redo_cores_layer(viewer, data=None, edge_width=2, shape_type="polygon"):
    """Create or replace the ``cores`` layer in a viewer.

    Args:
        viewer (napari.Viewer): Viewer instance to update.
        data (list, optional): Vertices describing the shapes. Defaults to ``[]``.
        shape_type (str, optional): Napari shape type. Defaults to ``"polygon"``.

    Returns:
        None
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
    """Create or replace the ``bounding_boxes`` layer in a viewer.

    Args:
        viewer (napari.Viewer): Viewer instance to update.
        data (list[list[float]], optional): Rectangle coordinates.
            Defaults to an empty list.
        text (list[str], optional): Labels shown next to rectangles.
            Defaults to an empty list.

    Returns:
        None
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


def display_saved_rois(viewer, IM_LEVEL, edge_width=2, save_path=None):
    """Load ROI annotations from disk and show them in the viewer.

    Args:
        viewer (napari.Viewer): Viewer instance where layers are added.
        IM_LEVEL (int): Image pyramid level used when the ROIs were saved.
        save_path (str, optional): File path of the saved ROIs. Defaults to ``None``.

    Returns:
        None
    """
    rect_list, poly_list, df = read_in_saved_rois(save_path, IM_LEVEL=IM_LEVEL)

    if len(rect_list) > 0:
        roi_names = df["roi_name"].tolist()
        shape_types = df.poly_type.to_list()
    else:
        roi_names = []
        shape_types = []
        viewer.status = "No previous rois found. Displaying empty layers."

    redo_bbox_layer(viewer, rect_list, edge_width=edge_width, text=roi_names)
    redo_cores_layer(viewer, poly_list, edge_width=edge_width, shape_type=shape_types)


def save_rois_from_viewer(viewer, org_im_shape, req_level, save_path=None):
    """Save ROIs drawn in the viewer to disk and update the displayed layers.

    Args:
        viewer (napari.Viewer): Viewer containing a ``cores`` shapes layer.
        org_im_shape (tuple[int, int]): Shape of the original image.
        req_level (int): Resolution level at which the ROIs are defined.
        save_path (str, optional): Destination CSV file path. Defaults to ``None``.

    Returns:
        None
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
