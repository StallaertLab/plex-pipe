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


# --- channels section: source (file_naming / manifest) and selection rules ---


def test_channels_section_optional_and_defaults():
    """No `channels:` section -> Cell DIVE naming, DAPI earliest, no other rules."""
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(base_cfg())
    ch = model.channels
    assert ch.file_naming == "celldive"
    assert ch.manifest is None
    assert ch.earliest_round_markers == ["DAPI"]
    assert ch.include_channels == ch.exclude_channels == []
    assert ch.use_markers == ch.ignore_markers == []


def test_bare_channels_section_means_defaults():
    """A bare `channels:` line in YAML (None) is the same as leaving it out."""
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(base_cfg(channels=None))
    assert model.channels.file_naming == "celldive"


@pytest.mark.parametrize("blank", [None, "", "  "])
def test_blank_channel_source_values_are_unset(blank):
    """A bare `key:` in YAML (None) or an empty string means "not set"."""
    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(channels={"file_naming": blank, "manifest": blank})
    model = AnalysisConfig.model_validate(cfg)
    assert model.channels.file_naming == "celldive"
    assert model.channels.manifest is None


def test_manifest_only():
    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(channels={"manifest": "/work/channels.csv"})
    model = AnalysisConfig.model_validate(cfg)
    assert model.channels.manifest == "/work/channels.csv"
    assert model.channels.file_naming is None


def test_file_naming_and_manifest_are_exclusive():
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(channels={"file_naming": "celldive", "manifest": "/work/c.csv"})
    with pytest.raises(ValidationError, match="not both"):
        AnalysisConfig.model_validate(cfg)


def test_unknown_file_naming_preset_rejected():
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg(channels={"file_naming": "phenocycler"})
    with pytest.raises(ValidationError, match="celldive"):
        AnalysisConfig.model_validate(cfg)


def test_every_registered_preset_is_accepted():
    """The schema takes its presets from NAMING_PRESETS (no hardcoded list)."""
    from plex_pipe.config.config_schema import AnalysisConfig
    from plex_pipe.io.channel_manifest import NAMING_PRESETS

    for name in NAMING_PRESETS:
        model = AnalysisConfig.model_validate(base_cfg(channels={"file_naming": name}))
        assert model.channels.file_naming == name


def test_earliest_round_markers_custom_and_blank():
    from plex_pipe.config.config_schema import AnalysisConfig

    custom = AnalysisConfig.model_validate(
        base_cfg(channels={"earliest_round_markers": ["Hoechst", "DAPI"]})
    )
    assert custom.channels.earliest_round_markers == ["Hoechst", "DAPI"]

    # a bare `earliest_round_markers:` in YAML means "none": latest round everywhere
    blank = AnalysisConfig.model_validate(
        base_cfg(channels={"earliest_round_markers": None})
    )
    assert blank.channels.earliest_round_markers == []


def test_selection_rules_in_channels():
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(
        base_cfg(channels={"ignore_markers": ["bCat"], "include_channels": None})
    )
    assert model.channels.ignore_markers == ["bCat"]
    assert model.channels.include_channels == []


@pytest.mark.parametrize(
    "rules",
    [
        {"include_channels": ["002_CD45", "003_CD45"]},
        {"include_channels": ["002_CD45"], "exclude_channels": ["002_CD45"]},
        {"include_channels": ["002_CD45"], "ignore_markers": ["CD45"]},
        {"include_channels": ["002_CD45"], "use_markers": ["DAPI"]},
        {"use_markers": ["CD45"], "ignore_markers": ["CD45"]},
    ],
)
def test_contradicting_selection_rules_fail_at_load(rules):
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    with pytest.raises(ValidationError, match="Contradicting channel selection"):
        AnalysisConfig.model_validate(base_cfg(channels=rules))


def test_non_contradicting_selection_rules_load():
    from plex_pipe.config.config_schema import AnalysisConfig

    model = AnalysisConfig.model_validate(
        base_cfg(
            channels={
                "include_channels": ["002_CD45", "001_CD45_1"],
                "exclude_channels": ["003_CD45"],
                "use_markers": ["CD45", "CD45_1"],
            }
        )
    )
    assert model.channels.include_channels == ["002_CD45", "001_CD45_1"]


def test_channel_marker():
    from plex_pipe.io.channel_manifest import channel_marker

    assert channel_marker("002_CD45") == "CD45"
    assert channel_marker("002_CD45_1") == "CD45_1"
    assert channel_marker("CD45") == "CD45"


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("roi_cutting", "ignore_markers", ["bCat"]),
        ("roi_cutting", "include_channels", ["001_DAPI"]),
        ("roi_cutting", "earliest_round_markers", ["Hoechst"]),
        ("general", "file_naming", "celldive"),
        ("general", "channel_manifest", "/work/c.csv"),
    ],
)
def test_keys_left_in_old_place_fail_clearly(section, key, value):
    """A 2.0 config with a channel key in its schema-1 place is an error that
    names the new place, instead of the key being silently ignored."""
    from pydantic import ValidationError

    from plex_pipe.config.config_schema import AnalysisConfig

    cfg = base_cfg()
    cfg[section] = {**cfg[section], key: value}
    with pytest.raises(ValidationError, match="moved from '" + section):
        AnalysisConfig.model_validate(cfg)


@pytest.mark.parametrize(
    "example",
    sorted((Path(__file__).parents[1] / "examples").glob("example_pipeline_config*.yaml")),
    ids=lambda p: p.name,
)
def test_example_configs_validate(example):
    """Shipped example configs are current (2.0) and validate as they are."""
    import yaml

    from plex_pipe.config.config_loaders import expand_pipeline
    from plex_pipe.config.config_migrations import (
        CURRENT_SCHEMA_VERSION,
        migrate_to_current,
    )
    from plex_pipe.config.config_schema import AnalysisConfig

    raw, start = migrate_to_current(yaml.safe_load(example.read_text()))
    assert start == CURRENT_SCHEMA_VERSION
    model = AnalysisConfig.model_validate(expand_pipeline(raw))
    assert model.channels.file_naming == "celldive"
