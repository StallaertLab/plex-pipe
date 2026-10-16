"""setup_example(): a ready-to-run example without a clone (offline tests).

The image download is replaced by a stub, so these tests need no network.
"""

from pathlib import Path

import pandas as pd
import pytest

import plex_pipe
from plex_pipe import datasets
from plex_pipe.config.config_loaders import load_config

REPO = Path(__file__).parents[1]


@pytest.fixture
def _no_download(monkeypatch):
    """Replaces fetch_example with a stub that writes two empty .tiff files."""

    def fake_fetch(dest):
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("a_DAPI.tiff", "b_CD45.tiff"):
            (dest / name).touch()
        return dest

    monkeypatch.setattr(datasets, "fetch_example", fake_fetch)


def test_packaged_config_matches_the_example_config():
    """The config shipped in the package is the repository's example config."""
    packaged = (REPO / "src/plex_pipe/example_config.yaml").read_text()
    example = (REPO / "examples/example_pipeline_config.yaml").read_text()
    assert packaged == example


@pytest.mark.usefixtures("_no_download")
def test_setup_example_writes_a_loadable_config_and_rois(tmp_path):
    config_path = plex_pipe.setup_example(tmp_path / "ex")

    assert config_path == (tmp_path / "ex" / "config.yaml").resolve()
    config = load_config(config_path)
    assert Path(config.general.image_dir) == (tmp_path / "ex" / "input").resolve()
    assert config.general.analysis_name == datasets.EXAMPLE_ANALYSIS_NAME
    assert (
        config.roi_info_file_path
        == (tmp_path / "ex" / "output" / "example" / "rois.pkl").resolve()
    )

    rois = pd.read_pickle(config.roi_info_file_path)
    assert list(rois["roi_name"]) == list(datasets.EXAMPLE_ROI_CORNERS)
    assert (rois["row_stop"] - rois["row_start"] == datasets.EXAMPLE_ROI_SIZE).all()
    assert config.roi_info_file_path.with_suffix(".csv").exists()


@pytest.mark.usefixtures("_no_download")
def test_setup_example_keeps_existing_files(tmp_path):
    config_path = plex_pipe.setup_example(tmp_path)
    edited = config_path.read_text().replace(
        'analysis_name: "example"', 'analysis_name: "example"  # edited'
    )
    config_path.write_text(edited)

    plex_pipe.setup_example(tmp_path)
    assert config_path.read_text() == edited


def test_config_paths_are_written_with_forward_slashes():
    """Windows paths must not become YAML escape sequences ("C:\\Users" -> \\U)."""
    text = datasets.example_config_text(
        Path("C:/Users/me/input"), Path("C:/Users/me/output")
    )
    assert 'image_dir: "C:/Users/me/input"' in text
    assert 'analysis_dir: "C:/Users/me/output"' in text
    assert "\\" not in text.split("channels:")[0]
