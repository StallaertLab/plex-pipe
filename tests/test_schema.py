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


def test_resolves_paths_and_defaults():
    """
    Verifies the 'after' model_validator computes derived paths and defaults
    (critical for reproducible file layout).
    """
    from plex_pipe.config.config_schema import AnalysisConfig

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
    from plex_pipe.config.config_schema import AnalysisConfig

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
    with pytest.raises(ValueError, match="Input 'MISSING' not found"):
        model.validate_pipeline(SDataStub())


# --- channel source: file_naming preset vs channel_manifest (step 3) ---


def _general(**fields):
    general = {"image_dir": "/im", "analysis_name": "A", "analysis_dir": "/work"}
    general.update(fields)
    return general


def test_channel_source_defaults_to_celldive():
    """Existing configs (neither key set) keep the Cell DIVE behaviour."""
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(base_cfg())
    assert model.general.file_naming == "celldive"
    assert model.general.channel_manifest is None


@pytest.mark.parametrize("blank", [None, "", "  "])
def test_blank_channel_source_values_are_unset(blank):
    """A bare `key:` in YAML (None) or an empty string means "not set"."""
    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(general=_general(file_naming=blank, channel_manifest=blank))
    model = AnalysisConfig.model_validate(cfg)
    assert model.general.file_naming == "celldive"
    assert model.general.channel_manifest is None


def test_channel_manifest_only():
    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(general=_general(channel_manifest="/work/channels.csv"))
    model = AnalysisConfig.model_validate(cfg)
    assert model.general.channel_manifest == "/work/channels.csv"
    assert model.general.file_naming is None


def test_file_naming_and_channel_manifest_are_exclusive():
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(
        general=_general(file_naming="celldive", channel_manifest="/work/c.csv")
    )
    with pytest.raises(ValidationError, match="not both"):
        AnalysisConfig.model_validate(cfg)


def test_unknown_file_naming_preset_rejected():
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(general=_general(file_naming="phenocycler"))
    with pytest.raises(ValidationError, match="celldive"):
        AnalysisConfig.model_validate(cfg)


def test_every_registered_preset_is_accepted():
    """The schema takes its presets from NAMING_PRESETS (no hardcoded list)."""
    from plex_pipe.config.config_schema import AnalysisConfig
    from plex_pipe.io.channel_manifest import NAMING_PRESETS

    for name in NAMING_PRESETS:
        model = AnalysisConfig.model_validate(
            base_cfg(general=_general(file_naming=name))
        )
        assert model.general.file_naming == name


@pytest.mark.parametrize(
    "example",
    sorted((Path(__file__).parents[1] / "examples").glob("example_pipeline_config*.yaml")),
    ids=lambda p: p.name,
)
def test_example_configs_still_validate(example):
    """Shipped example configs load unchanged (no schema_version bump needed)."""
    import yaml

    from plex_pipe.config.config_loaders import expand_pipeline
    from plex_pipe.config.config_migrations import migrate_to_current
    from plex_pipe.config.config_schema import AnalysisConfig

    raw, _ = migrate_to_current(yaml.safe_load(example.read_text()))
    model = AnalysisConfig.model_validate(expand_pipeline(raw))
    assert model.general.file_naming == "celldive"


# --- roi_cutting.earliest_round_markers ---


def _cutting(**fields):
    cutting = {"roi_dir_tif": None, "roi_dir_output": None, "margin": 8, "mask_value": 1}
    cutting.update(fields)
    return cutting


def test_earliest_round_markers_defaults_to_dapi():
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(base_cfg())
    assert model.roi_cutting.earliest_round_markers == ["DAPI"]


def test_earliest_round_markers_custom_and_blank():
    from plex_pipe.config.config_schema import AnalysisConfig

    custom = AnalysisConfig.model_validate(
        base_cfg(roi_cutting=_cutting(earliest_round_markers=["Hoechst", "DAPI"]))
    )
    assert custom.roi_cutting.earliest_round_markers == ["Hoechst", "DAPI"]

    # a bare `earliest_round_markers:` in YAML means "none": latest round everywhere
    blank = AnalysisConfig.model_validate(
        base_cfg(roi_cutting=_cutting(earliest_round_markers=None))
    )
    assert blank.roi_cutting.earliest_round_markers == []
