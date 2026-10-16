"""Silence known, harmless messages from the libraries PlexPipe calls.

Each context manager applies only inside its ``with`` block, so the user's own
warning and logging settings, and messages from other code, are left alone.
Only messages checked to be harmless are listed here; anything else still shows.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import anndata as ad

#: Warnings raised while an InstanSeg model loads and runs: (category, message regex).
_MODEL_WARNINGS: tuple[tuple[type[Warning], str], ...] = (
    # No CUDA GPU (CPU or Apple MPS): InstanSeg runs in full precision instead.
    (UserWarning, r"CUDA is not available or torch_xla is imported"),
    # torch deprecation inside InstanSeg's model loading; for InstanSeg to update.
    (FutureWarning, r"`torch\.jit\.load` is deprecated"),
    # torch's "beta feature" notice, triggered inside the InstanSeg model.
    (UserWarning, r"Sparse CSR tensor support is in beta state"),
)


@contextmanager
def quiet_model() -> Iterator[None]:
    """Hides the harmless torch/InstanSeg warnings listed in ``_MODEL_WARNINGS``."""
    with warnings.catch_warnings():
        for category, message in _MODEL_WARNINGS:
            warnings.filterwarnings("ignore", message=message, category=category)
        yield


@contextmanager
def quiet_zarr_io() -> Iterator[None]:
    """Hides harmless messages while SpatialData stores are read or written.

    * anndata warns on every table array written to Zarr v3 until a sharding
      choice is made. PlexPipe makes the choice explicit: no sharding, the
      layout it has always written.
    * ome-zarr logs ``no parent found for <Label>`` for each labels element of
      a SpatialData store, because SpatialData does not keep the image/labels
      nesting the ome-zarr reader looks for. The store reads correctly.
    """
    ome_zarr_logger = logging.getLogger("ome_zarr.reader")
    previous_level = ome_zarr_logger.level
    ome_zarr_logger.setLevel(logging.ERROR)
    try:
        with ExitStack() as stack:
            if hasattr(ad.settings, "auto_shard_zarr_v3"):  # anndata >= 0.12
                stack.enter_context(ad.settings.override(auto_shard_zarr_v3=False))
            yield
    finally:
        ome_zarr_logger.setLevel(previous_level)
