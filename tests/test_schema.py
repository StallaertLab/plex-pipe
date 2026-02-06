from pathlib import Path

import pytest


def base_cfg(**overrides):
    """Minimal valid analysis config dict; callers can override fields as needed."""
    cfg = {
        "general": {
            "image_dir": "/im",
            "analysis_name": "A",
            "analysis_dir": "/work/analysis",
        },
        "roi_definition": {
            "detection_image": "I0",
            "roi_info_file_path": None,
            "im_level": 0,
        },
        "roi_cutting": {
            "roi_dir_tif": None,
            "roi_dir_output": None,
            "include_channels": None,
            "exclude_channels": None,
            "use_markers": None,
            "ignore_markers": None,
            "margin": 8,
            "mask_value": 1,
            "transfer_cleanup_enabled": False,
            "roi_cleanup_enabled": False,
        },
        "additional_elements": [],
        "qc": {"prefix": "Q"},
        "quant": [{"name": "q1", "masks": {"m": "L"}, "layer_connection": None}],
        "sdata_storage": {
            "chunk_size": [1, 512, 512],
            "max_pyramid_level": 4,
            "downscale": 2,
        },
    }
    # shallow updates only where provided
    for k, v in overrides.items():
        cfg[k] = v
    return cfg


def test_resolves_paths_and_defaults(tmp_path, monkeypatch):
    """
    Verifies the 'after' model_validator computes derived paths and defaults
    (critical for reproducible file layout).
    """
    from plex_pipe.utils.config_schema import AnalysisConfig

    cfg = base_cfg()
    model = AnalysisConfig.model_validate(cfg)

    base = Path(cfg["general"]["analysis_dir"]) / cfg["general"]["analysis_name"]

    assert Path(model.analysis_dir) == base
    assert Path(model.log_dir_path) == base / "logs"
    assert Path(model.roi_info_file_path) == base / "rois.pkl"
    assert Path(model.roi_dir_tif_path) == base / "temp"
    assert Path(model.roi_dir_output_path) == base / "rois"


def test_validate_pipeline_detects_missing_inputs():
    """
    Validates that pipeline steps cannot consume non-existent layers; this
    fails fast before running operations, preventing wasted computation.
    """
    from plex_pipe.utils.config_schema import AnalysisConfig

    # Stub with minimal interface used by validate_pipeline()
    class SDataStub:
        images = {"I0"}
        labels = {"L0"}

    cfg = base_cfg(
        additional_elements=[
            {"category": "mask_builder", "type": "blob", "input": "I0", "output": "L1"},
            {
                "category": "mask_builder",
                "type": "blob",
                "input": "MISSING",
                "output": "O0",
            },
        ]
    )

    model = AnalysisConfig.model_validate(cfg)
    with pytest.raises(ValueError) as ei:
        model.validate_pipeline(SDataStub())

    assert "Input 'MISSING' not found" in str(ei.value)
