import napari
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from plex_pipe.core_definition.roi_utils import xywh_to_corners
from plex_pipe.widgets.viewer_utils import (
    display_saved_rois,
    save_rois_from_viewer,
)


class RoiWidget(QWidget):
    def __init__(
        self, napari_viewer, im_list, im_level, save_path, org_im_shape
    ) -> None:
        super().__init__()
        self.viewer = napari_viewer
        self.im_list = im_list
        self.im_level = im_level
        self.save_path = save_path
        self.org_im_shape = org_im_shape

        # Default state
        self.edge_width = 2

        self.setLayout(QVBoxLayout())
        group = QGroupBox("ROI Controls")
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)

        # 1. Edge Width Slider
        group_layout.addLayout(self.create_edge_width_layout())

        # 2. Display Button
        self.display_btn = QPushButton("Display Saved ROIs")
        self.display_btn.clicked.connect(self._on_display_clicked)
        group_layout.addWidget(self.display_btn)

        # 3. Save Button
        self.save_btn = QPushButton("Save ROIs")
        self.save_btn.clicked.connect(self._on_save_clicked)
        group_layout.addWidget(self.save_btn)

        self.layout().addWidget(group)
        self.layout().addStretch()  # Pushes everything to the top

        # display the data
        self.add_layers()

    @classmethod
    def from_config(cls, viewer, config):

        from pathlib import Path

        from plex_pipe.utils.im_utils import (
            get_all_resolutions,
            get_org_im_shape,
            get_small_image,
        )

        im_level = config.roi_definition.im_level or 0
        image_path = (
            Path(config.general.image_dir) / config.roi_definition.detection_image
        )

        # 2. Prepare the data for the widget
        im_list = (
            get_all_resolutions(image_path)
            if config.roi_definition.im_level is None
            else [get_small_image(image_path, req_level=int(im_level))]
        )
        org_im_shape = get_org_im_shape(image_path)

        # 3. Create and return the widget instance
        return cls(
            napari_viewer=viewer,
            im_list=im_list,
            im_level=im_level,
            save_path=config.roi_info_file_path,
            org_im_shape=org_im_shape,
        )

    def add_layers(self):

        self.viewer.add_image(self.im_list, name="signal")

        # add a red rectangle to frame the image
        frame_rect = xywh_to_corners(
            [0, 0, self.im_list[0].shape[1], self.im_list[0].shape[0]]
        )
        self.viewer.add_shapes(
            frame_rect,
            edge_color="white",
            face_color="transparent",
            shape_type="rectangle",
            edge_width=self.edge_width,
            name="frame",
        )

        # add a layer for the saved rois
        display_saved_rois(
            self.viewer,
            IM_LEVEL=self.im_level,
            save_path=self.save_path,
            edge_width=self.edge_width,
        )

    def create_edge_width_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.label = QLabel("Edge Width")

        self.spinbox = QSpinBox()
        self.spinbox.setRange(0, 200)
        self.spinbox.setValue(self.edge_width)

        # When spinbox changes, update slider
        self.spinbox.valueChanged.connect(self._on_width_change)

        # Add them to the layout in order
        layout.addWidget(self.label)
        layout.addWidget(self.spinbox)

        return layout

    def _on_width_change(self, value):
        self.edge_width = value

        for layer in self.viewer.layers:
            if isinstance(layer, napari.layers.Shapes):
                layer.edge_width = self.edge_width
                layer.refresh()

    def _on_display_clicked(self):
        display_saved_rois(
            self.viewer, IM_LEVEL=self.im_level, save_path=self.save_path
        )

    def _on_save_clicked(self):
        save_rois_from_viewer(
            self.viewer,
            org_im_shape=self.org_im_shape,
            req_level=self.im_level,
            save_path=self.save_path,
        )
