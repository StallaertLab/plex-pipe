from functools import partial
from typing import Any

import numpy as np
from geopandas import GeoDataFrame
from qtpy.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shapely import Polygon
from spatialdata.models import ShapesModel
from spatialdata.transformations import Identity


class QCWidget(QWidget):
    """Widget for Quality Control of spatial data images and shapes."""

    def __init__(self, napari_viewer: Any, sdata: Any) -> None:
        """Initializes the QCWidget.

        Args:
            napari_viewer: The napari viewer instance.
            sdata: The SpatialData object containing images and shapes.
        """
        super().__init__()
        self.setLayout(QVBoxLayout())

        self.position = 0
        self.viewer = napari_viewer
        self.camera_center = None
        self.camera_zoom = None
        self.sdata = sdata
        self.im_list = sorted(sdata.images.keys())
        self.len = len(self.im_list)
        self.im_name = self.im_list[self.position]
        self.shapes_name = f"qc_exclude_{self.im_name}"

        navigation_group = QGroupBox()
        navigation_group.setLayout(QVBoxLayout())

        navigation_group.layout().addWidget(QLabel("QC:"))

        # add navigation row
        self.navigation_row = self.add_navigation_control()
        navigation_group.layout().addWidget(self.navigation_row)

        # add saving buttons
        save_btn = self.add_save_btn()
        navigation_group.layout().addWidget(save_btn)

        save_all_btn = self.add_save_all_btn()
        navigation_group.layout().addWidget(save_all_btn)

        self.layout().addWidget(navigation_group)

        if self.len:
            self.show_current()
        self.update_position_label()

    def update_position_label(self) -> None:
        """Updates the label showing the current image position."""
        if self.len:
            self.position_label.setText(f"Position: {self.position}/{self.len - 1}")
        else:
            self.position_label.setText("No images loaded")

    def add_navigation_control(self) -> QWidget:
        """Creates the navigation control widget.

        Returns:
            A QWidget containing navigation buttons and dropdown.
        """

        navigation_row = QWidget()
        navigation_row.setLayout(QGridLayout())

        self.backward_btn = self.add_backward_btn()
        self.forward_btn = self.add_forward_btn()
        self.combo = self.add_dropdown()
        self.position_label = QLabel()

        navigation_row.layout().addWidget(self.backward_btn, 0, 0)
        navigation_row.layout().addWidget(self.combo, 0, 1)
        navigation_row.layout().addWidget(self.forward_btn, 0, 2)
        navigation_row.layout().addWidget(self.position_label, 1, 1)

        return navigation_row

    def add_backward_btn(self) -> QPushButton:
        """Creates the backward navigation button.

        Returns:
            The configured backward QPushButton.
        """
        backward_btn = QPushButton("<")

        backward_btn.clicked.connect(partial(self.step, True))

        return backward_btn

    def add_forward_btn(self) -> QPushButton:
        """Creates the forward navigation button.

        Returns:
            The configured forward QPushButton.
        """
        forward_btn = QPushButton(">")

        forward_btn.clicked.connect(partial(self.step, False))

        return forward_btn

    def on_choice(self, text: str) -> None:
        """Handles image selection from the dropdown.

        Args:
            text: The name of the selected image.
        """
        # save shapes
        self.remember_shapes()

        # remember camera
        self.remember_display()

        # read in the position
        self.position = self.im_list.index(text)

        # update display
        self.update_display()

    def add_dropdown(self) -> QComboBox:
        """Creates the image selection dropdown.

        Returns:
            The configured QComboBox.
        """
        combo = QComboBox()
        combo.addItems(self.im_list)

        combo.currentTextChanged.connect(self.on_choice)

        return combo

    def clear_viewer(self) -> None:
        """Removes all layers from the viewer."""
        for layer in list(self.viewer.layers):
            self.viewer.layers.remove(layer)

    def datatree_to_dask_list(self, ms_tree: Any) -> list[Any]:
        """Converts a multiscale tree to a list of dask arrays.

        Args:
            ms_tree: The multiscale tree object.

        Returns:
            A list of image data arrays sorted by scale.
        """

        def scale_idx(key: str) -> int:
            try:
                return int(key.replace("scale", ""))
            except ValueError:
                return 0

        items = sorted(ms_tree.items(), key=lambda kv: scale_idx(kv[0]))

        levels = []
        for _, node in items:
            da = next(iter(node.data_vars.values()))
            levels.append(da.data)
        return levels

    def show_current(self) -> None:
        """Displays the current image and associated shapes in the viewer."""
        levels = self.datatree_to_dask_list(self.sdata.images[self.im_name])

        self.viewer.add_image(
            levels,
            visible=True,
            name=self.im_name,
            blending="additive",
            contrast_limits=self.sdata[self.im_name].attrs.get("contrast"),
        )

        if self.shapes_name in self.sdata:
            data = [
                np.array(self.sdata[self.shapes_name].geometry[i].exterior.coords)[
                    :, ::-1
                ]
                for i in range(len(self.sdata[self.shapes_name]))
            ]
        else:
            data = []
        self.shapes_layer = self.viewer.add_shapes(
            data=data, name=self.shapes_name, shape_type="polygon"
        )

        if self.camera_center:
            self.viewer.camera.center = self.camera_center
            self.viewer.camera.zoom = self.camera_zoom

    def update_display(self) -> None:
        """Updates the viewer to show the currently selected image."""
        # updata current names
        self.im_name = self.im_list[self.position]
        self.shapes_name = f"qc_exclude_{self.im_name}"

        # clear viewer
        self.clear_viewer()

        # load new data
        self.show_current()

        # update label
        self.update_position_label()

    def remember_display(self) -> None:
        """Saves the current camera settings and contrast limits."""
        # remember camera settings
        self.camera_center = self.viewer.camera.center
        self.camera_zoom = self.viewer.camera.zoom

        # remember channel settings
        layer = self.viewer.layers[self.im_name]
        contrast = layer.contrast_limits

        self.sdata[self.im_name].attrs["contrast"] = contrast

    def step(self, backward: bool = False) -> None:
        """Steps to the next or previous image.

        Args:
            backward: If True, move to the previous image. Otherwise, move forward.
        """
        # save shapes
        self.remember_shapes()

        # remember camera
        self.remember_display()

        if backward:
            if self.position == 0:
                return
            else:
                self.position -= 1
        else:
            if self.position == self.len - 1:
                return
            else:
                self.position += 1

        # update display
        self.update_display()

        # update combo box
        self.combo.blockSignals(True)
        self.combo.setCurrentText(self.im_name)
        self.combo.blockSignals(False)

    def numpy_to_shapely(self, x: np.ndarray) -> Polygon:
        """Converts a numpy array of coordinates to a Shapely Polygon.

        Args:
            x: Numpy array of coordinates.

        Returns:
            A Shapely Polygon.
        """
        x = x[..., -2:][:, ::-1]
        return Polygon(list(map(tuple, x)))

    def remember_shapes(self) -> None:
        """Saves the current shapes from the viewer to the SpatialData object."""
        if self.shapes_name in [x.name for x in self.viewer.layers]:

            if self.viewer.layers[self.shapes_name].data:
                gdf = GeoDataFrame(
                    {
                        "geometry": [
                            self.numpy_to_shapely(x)
                            for x in self.viewer.layers[self.shapes_name].data
                        ]
                    }
                )
                gdf = ShapesModel.parse(gdf, transformations={"global": Identity()})
                self.sdata.shapes[self.shapes_name] = gdf
            else:
                if self.shapes_name in self.sdata:
                    del self.sdata[self.shapes_name]

    def add_save_btn(self) -> QPushButton:
        """Creates the save button for the current layer.

        Returns:
            The configured save QPushButton.
        """
        save_btn = QPushButton("Save")

        save_btn.clicked.connect(self.save_shapes_layer)
        save_btn.setToolTip("Overwrite shapes on disk for the current layer.")

        return save_btn

    def re_save_element(self, element: str) -> None:
        """Overwrites a specific element in the SpatialData object on disk.

        Args:
            element: The name of the element to save.
        """
        if f"shapes/{element}" in self.sdata.elements_paths_on_disk():
            self.sdata.delete_element_from_disk(element)

        self.sdata.write_element(element)

    def save_shapes_layer(self) -> None:
        """Saves the current shapes layer to disk."""
        self.remember_shapes()

        self.re_save_element(self.shapes_name)

        self.viewer.status = f"{self.shapes_name} has been saved to disk."

    def add_save_all_btn(self) -> QPushButton:
        """Creates the button to save all shapes.

        Returns:
            The configured save all QPushButton.
        """
        save_all_btn = QPushButton("Save All")

        save_all_btn.clicked.connect(self.save_shapes_all)
        save_all_btn.setToolTip("Overwrite all shapes on disk.")

        return save_all_btn

    def save_shapes_all(self) -> None:
        """Saves all shape elements to disk."""
        self.remember_shapes()
        for element in list(self.sdata.shapes.keys()):
            self.re_save_element(element)

        self.viewer.status = "All shapes have been saved to disk."

    def create_global_mask(self) -> None:
        """Placeholder for creating a global mask."""
