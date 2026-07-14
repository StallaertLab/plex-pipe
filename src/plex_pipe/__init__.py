try:
    from ._version import __version__
except ImportError:  # _version.py is generated at build time by setuptools_scm
    __version__ = "0.0.0+unknown"

from plex_pipe.config.config_loaders import load_config, migrate_config
from plex_pipe.datasets import fetch_example
from plex_pipe.stages.quantification.controller import QuantificationController
from plex_pipe.stages.quantification.qc_shape_masker import QcShapeMasker
from plex_pipe.stages.resource_building.controller import (
    ResourceBuildingController,
)
from plex_pipe.stages.roi_preparation.controller import (
    RoiPreparationController,
)
from plex_pipe.stages.roi_preparation.file_strategy import (
    GlobusFileStrategy,
    LocalFileStrategy,
)

from . import ops

__all__ = [
    "__version__",
    "ops",
    "load_config",
    "migrate_config",
    "fetch_example",
    "RoiPreparationController",
    "ResourceBuildingController",
    "QuantificationController",
    "QcShapeMasker",
    "GlobusFileStrategy",
    "LocalFileStrategy",
]
