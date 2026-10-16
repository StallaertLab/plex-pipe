"""The top-level package imports its public names lazily (plex_pipe/__init__.py)."""

import subprocess
import sys

import plex_pipe


def test_public_names_resolve():
    """Every name in __all__ can be imported from plex_pipe."""
    assert set(plex_pipe.__all__) == {"__version__", "ops", *plex_pipe._LAZY}
    for name in plex_pipe.__all__:
        assert getattr(plex_pipe, name) is not None


def test_import_is_light():
    """`import plex_pipe` does not load the scientific stack (keeps the CLI fast)."""
    code = (
        "import sys, plex_pipe; "
        "print(sorted(m for m in ('spatialdata', 'dask', 'anndata', 'torch') "
        "if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
