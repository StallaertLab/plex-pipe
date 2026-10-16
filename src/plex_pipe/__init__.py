"""PlexPipe: from multiplexed whole-slide images to single-cell data.

The public names below are imported on first use (PEP 562 ``__getattr__``), so
``import plex_pipe`` and ``plexpipe --version`` stay fast; the scientific stack
(spatialdata, dask, torch, ...) loads only when a function or class needs it.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

try:
    from ._version import __version__
except ImportError:  # _version.py is generated at build time by setuptools_scm
    __version__ = "0.0.0+unknown"

if TYPE_CHECKING:  # for type checkers, IDEs and the API docs
    from plex_pipe import ops
    from plex_pipe.config.config_loaders import (
        load_config,
        migrate_config,
        save_config_snapshot,
    )
    from plex_pipe.datasets import fetch_example
    from plex_pipe.stages.quantification.controller import QuantificationController
    from plex_pipe.stages.quantification.qc_shape_masker import QcShapeMasker
    from plex_pipe.stages.resource_building.controller import (
        ResourceBuildingController,
    )
    from plex_pipe.stages.roi_preparation.channel_scanner import (
        preview_channels,
        save_manifest,
    )
    from plex_pipe.stages.roi_preparation.controller import (
        RoiPreparationController,
    )
    from plex_pipe.stages.roi_preparation.file_strategy import (
        GlobusFileStrategy,
        LocalFileStrategy,
    )

#: Public name -> module that defines it.
_LAZY = {
    "load_config": "plex_pipe.config.config_loaders",
    "migrate_config": "plex_pipe.config.config_loaders",
    "save_config_snapshot": "plex_pipe.config.config_loaders",
    "fetch_example": "plex_pipe.datasets",
    "RoiPreparationController": "plex_pipe.stages.roi_preparation.controller",
    "ResourceBuildingController": "plex_pipe.stages.resource_building.controller",
    "QuantificationController": "plex_pipe.stages.quantification.controller",
    "QcShapeMasker": "plex_pipe.stages.quantification.qc_shape_masker",
    "GlobusFileStrategy": "plex_pipe.stages.roi_preparation.file_strategy",
    "LocalFileStrategy": "plex_pipe.stages.roi_preparation.file_strategy",
    "preview_channels": "plex_pipe.stages.roi_preparation.channel_scanner",
    "save_manifest": "plex_pipe.stages.roi_preparation.channel_scanner",
}

__all__ = [
    "__version__",
    "ops",
    "load_config",
    "migrate_config",
    "save_config_snapshot",
    "fetch_example",
    "RoiPreparationController",
    "ResourceBuildingController",
    "QuantificationController",
    "QcShapeMasker",
    "GlobusFileStrategy",
    "LocalFileStrategy",
    "preview_channels",
    "save_manifest",
]


def __getattr__(name: str) -> Any:
    """Imports a public name the first time it is used."""
    if name == "ops":
        value: Any = import_module("plex_pipe.ops")
    elif name in _LAZY:
        value = getattr(import_module(_LAZY[name]), name)
    else:
        raise AttributeError(f"module 'plex_pipe' has no attribute {name!r}")
    globals()[name] = value  # cache: later lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
