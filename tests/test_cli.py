"""Tests for the plexpipe command line (one channel / one ROI per call)."""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import spatialdata as sd
import tifffile
import yaml

from plex_pipe import cli
from plex_pipe.config.config_loaders import load_config
from plex_pipe.runners import (
    build_quant_controllers,
    build_resource_controllers,
)
from plex_pipe.stages.roi_preparation.controller import (
    RoiPreparationController,
)
from plex_pipe.stages.roi_preparation.file_strategy import LocalFileStrategy

EXAMPLE_CONFIG = Path(__file__).parents[1] / "examples" / "example_pipeline_config.yaml"

# Cell DIVE names; bCat is ignored by the example config
FILES = {
    "DAPI": "sample_1.0.4_R000_DAPI__FINAL_F.tiff",
    "CD45": "sample_1.0.4_R000_Cy5_CD45-AF647_FINAL_AFR_F.tiff",
    "NaKATPase": "sample_1.0.4_R000_Cy7_NaKATPase-AF750_FINAL_AFR_F.tiff",
    "bCat": "sample_1.0.4_R000_Cy3_bCat-AF555_FINAL_AFR_F.tiff",
}


@pytest.fixture
def _in_tmp(tmp_path, monkeypatch):
    """Runs from tmp_path/run, so the example config's relative
    ``../examples/output`` folders are created inside tmp_path."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.chdir(run_dir)


@pytest.fixture
def analysis(tmp_path):
    """Small images, a ROI table and an absolute-path config."""
    image_dir = tmp_path / "input"
    image_dir.mkdir()
    for i, fname in enumerate(FILES.values()):
        img = (np.arange(64 * 64).reshape(64, 64) + i).astype(np.uint16)
        tifffile.imwrite(image_dir / fname, img)

    rois = pd.DataFrame(
        {
            "roi_name": ["ROI_000", "ROI_001"],
            "row_start": [0, 32],
            "row_stop": [16, 48],
            "column_start": [0, 32],
            "column_stop": [16, 48],
            "poly_type": ["rectangle", "rectangle"],
        }
    )

    def make_config(name):
        analysis_dir = tmp_path / name
        analysis_dir.mkdir()
        rois.to_pickle(analysis_dir / "rois.pkl")
        cfg = yaml.safe_load(EXAMPLE_CONFIG.read_text())
        cfg["general"]["image_dir"] = str(image_dir)
        cfg["general"]["analysis_dir"] = str(tmp_path)
        cfg["general"]["analysis_name"] = name
        cfg["roi_cutting"]["roi_cleanup_enabled"] = False
        cfg["sdata_storage"]["chunk_size"] = [1, 8, 8]
        cfg["sdata_storage"]["max_pyramid_level"] = 1
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(cfg))
        return path

    return make_config


def run_per_unit(config_path, out_dir):
    """Runs setup, cut-image per channel and assemble-roi per ROI."""
    cli.main(["setup", "--exp_config", str(config_path), "--out_dir", str(out_dir)])
    images = cli.read_images_file(out_dir / cli.IMAGES_FILE)
    for row in images:
        cli.main(
            [
                "cut-image",
                "--exp_config",
                str(config_path),
                "--channel",
                row["channel"],
                "--image_path",
                row["path"],
            ]
        )
    with open(out_dir / cli.ROIS_FILE, newline="") as f:
        rois = list(csv.DictReader(f))
    for row in rois:
        cli.main(
            [
                "assemble-roi",
                "--exp_config",
                str(config_path),
                "--roi",
                row["roi_name"],
                "--images",
                str(out_dir / cli.IMAGES_FILE),
            ]
        )
    return images, rois


def test_setup_writes_image_and_roi_lists(analysis, tmp_path):
    config_path = analysis("per_unit")
    out_dir = tmp_path / "work"
    cli.main(["setup", "--exp_config", str(config_path), "--out_dir", str(out_dir)])

    images = cli.read_images_file(out_dir / cli.IMAGES_FILE)
    assert {r["channel"] for r in images} == {"DAPI", "CD45", "NaKATPase"}
    assert all(r["task_id"] == "" for r in images)

    rois = pd.read_csv(out_dir / cli.ROIS_FILE)
    assert rois["roi_name"].tolist() == ["ROI_000", "ROI_001"]
    assert rois["path"].tolist() == [
        str(tmp_path / "per_unit" / "rois" / "ROI_000.zarr"),
        str(tmp_path / "per_unit" / "rois" / "ROI_001.zarr"),
    ]


def test_per_unit_matches_controller(analysis, tmp_path):
    """Per-unit commands give the same ROIs as the one-process controller."""
    _, rois = run_per_unit(analysis("per_unit"), tmp_path / "work")

    config = load_config(analysis("controller"))
    RoiPreparationController(
        metadata_df=pd.read_pickle(config.roi_info_file_path),
        file_strategy=LocalFileStrategy(config=config),
        temp_dir=str(config.roi_dir_tif_path),
        output_dir=str(config.roi_dir_output_path),
        max_pyramid_levels=config.sdata_storage.max_pyramid_level,
        chunk_size=config.sdata_storage.chunk_size,
        downscale=config.sdata_storage.downscale,
        temp_roi_delete=False,
    ).run()

    for row in rois:
        a = sd.read_zarr(row["path"])
        b = sd.read_zarr(config.roi_dir_output_path / f"{row['roi_name']}.zarr")
        assert set(a.images) == set(b.images) == {"DAPI", "CD45", "NaKATPase"}
        for ch in a.images:
            np.testing.assert_array_equal(a.images[ch].values, b.images[ch].values)


def test_assemble_roi_fails_if_a_channel_is_missing(analysis, tmp_path):
    config_path = analysis("per_unit")
    out_dir = tmp_path / "work"
    run_per_unit(config_path, out_dir)
    (tmp_path / "per_unit" / "temp" / "ROI_001" / "CD45.tiff").unlink()

    with pytest.raises(ValueError, match=r"missing channels \['CD45'\]"):
        cli.main(
            [
                "assemble-roi",
                "--exp_config",
                str(config_path),
                "--roi",
                "ROI_001",
                "--images",
                str(out_dir / cli.IMAGES_FILE),
            ]
        )


@pytest.mark.usefixtures("_in_tmp")
def test_relative_paths_are_rejected():
    with pytest.raises(ValueError, match="must be absolute"):
        cli.main(["setup", "--exp_config", str(EXAMPLE_CONFIG)])


def test_cut_image_deletes_only_transferred_images(analysis, tmp_path):
    config_path = analysis("per_unit")
    config = load_config(config_path)
    original = tmp_path / "input" / FILES["DAPI"]
    transferred = config.temp_dir / FILES["DAPI"]
    transferred.write_bytes(original.read_bytes())

    for path in (original, transferred):
        cli.main(
            [
                "cut-image",
                "--exp_config",
                str(config_path),
                "--channel",
                "DAPI",
                "--image_path",
                str(path),
                "--cleanup",
            ]
        )
    assert original.exists()
    assert not transferred.exists()


@pytest.mark.usefixtures("_in_tmp")
def test_builders_follow_the_config():
    config = load_config(EXAMPLE_CONFIG)
    quant = build_quant_controllers(config)
    assert [c.table_name for c in quant] == ["instanseg_table"]

    # keep only steps that need no segmentation model
    config.additional_elements = [
        s for s in config.additional_elements if s.category != "object_segmenter"
    ]
    steps = build_resource_controllers(config, overwrite=True)
    assert len(steps) == len(config.additional_elements)
    assert all(s.overwrite for s in steps)


def test_wait_for_globus_task():
    class FakeTC:
        def __init__(self, statuses):
            self.statuses = iter(statuses)

        def get_task(self, task_id):
            return {"status": next(self.statuses)}

    cli.wait_for_globus_task(FakeTC(["ACTIVE", "SUCCEEDED"]), "t", 1, 0)
    with pytest.raises(RuntimeError, match="failed"):
        cli.wait_for_globus_task(FakeTC(["ACTIVE", "FAILED"]), "t", 1, 0)
    with pytest.raises(TimeoutError):
        cli.wait_for_globus_task(FakeTC(["ACTIVE"] * 3), "t", 0, 0)
