"""Tests for schema versioning and the config migration chain."""

from pathlib import Path

import pytest
import yaml

from plex_pipe.config.config_migrations import (
    CURRENT_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION_STR,
    LEGACY_VERSION,
    _detect_version,
    format_version,
    migrate_to_current,
    migrate_v0_to_v1,
    migrate_v1_to_v2,
    needs_migration,
    parse_version,
)

LEGACY_FIXTURE = Path(__file__).parent / "example_data" / "legacy_config_v0.yaml"
V1_FIXTURE = Path(__file__).parent / "example_data" / "config_v1.yaml"


def _load_legacy_raw():
    """Read the real legacy (v0) config fixture as a raw dict."""
    with open(LEGACY_FIXTURE) as f:
        return yaml.safe_load(f)


# --- version detection -------------------------------------------------------


def test_absent_schema_version_is_legacy():
    """A config with no schema_version key is treated as legacy (0.0)."""
    assert _detect_version({}) == LEGACY_VERSION == (0, 0)


def test_current_version_is_2_0():
    assert CURRENT_SCHEMA_VERSION == (2, 0)
    assert CURRENT_SCHEMA_VERSION_STR == "2.0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.0", (2, 0)),  # preferred: quoted MAJOR.MINOR
        ("2.10", (2, 10)),  # quoted, so 10 is not read as 1
        ("2", (2, 0)),
        (" 2.1 ", (2, 1)),
        (1, (1, 0)),  # integer written by schema 1
        (2.0, (2, 0)),  # unquoted YAML number
    ],
)
def test_parse_version(value, expected):
    assert parse_version(value) == expected
    assert _detect_version({"schema_version": value}) == expected


@pytest.mark.parametrize("bad", ["x", "2.0.1", "v2", True, None, [2, 0], -1])
def test_invalid_schema_version_raises(bad):
    """Anything that is not MAJOR.MINOR is rejected with a clear message."""
    with pytest.raises(ValueError, match="MAJOR.MINOR"):
        parse_version(bad)


def test_format_version():
    assert format_version((2, 0)) == "2.0"
    assert format_version((2, 10)) == "2.10"


def test_needs_migration_compares_major_only():
    """Only an older MAJOR needs a migration; MINOR never does."""
    assert needs_migration((0, 0)) is True
    assert needs_migration((1, 0)) is True
    assert needs_migration((2, 0)) is False
    assert needs_migration((2, 3)) is False


# --- the v0 -> v1 migration --------------------------------------------------


@pytest.mark.parametrize("legacy_cat", ["image_filter", "image_transformer"])
def test_v0_to_v1_renames_enhancer_category(legacy_cat):
    """Both legacy enhancer category names become `image_enhancer`."""
    raw = {
        "additional_elements": [
            {"category": legacy_cat, "type": "normalize"},
            {"category": "object_segmenter", "type": "instanseg"},
        ]
    }
    out = migrate_v0_to_v1(raw)
    assert out["additional_elements"][0]["category"] == "image_enhancer"
    assert out["additional_elements"][1]["category"] == "object_segmenter"
    assert out["schema_version"] == 1


def test_v0_to_v1_is_defensive_on_new_shape():
    """Running v0->v1 on already-v1-shaped input is a safe no-op (+ stamps 1)."""
    raw = {"additional_elements": [{"category": "image_enhancer"}]}
    out = migrate_v0_to_v1(raw)
    assert out["additional_elements"][0]["category"] == "image_enhancer"
    assert out["schema_version"] == 1


def test_v0_to_v1_handles_missing_additional_elements():
    """Migration does not crash when additional_elements is absent or None."""
    assert migrate_v0_to_v1({})["schema_version"] == 1
    assert migrate_v0_to_v1({"additional_elements": None})["schema_version"] == 1


# --- migrate_to_current ------------------------------------------------------


def test_migrate_legacy_to_current():
    """An unversioned config is brought up to the current schema."""
    raw = {"additional_elements": [{"category": "image_transformer"}]}
    migrated, start = migrate_to_current(raw)
    assert start == (0, 0)
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION_STR
    assert migrated["additional_elements"][0]["category"] == "image_enhancer"


def test_already_current_is_unchanged():
    """A config already at the current version passes through untouched."""
    raw = {"schema_version": CURRENT_SCHEMA_VERSION_STR, "additional_elements": []}
    migrated, start = migrate_to_current(raw)
    assert start == CURRENT_SCHEMA_VERSION
    assert migrated == raw


def test_future_version_raises_clear_error():
    """A config newer than this build understands raises a readable error."""
    raw = {"schema_version": f"{CURRENT_SCHEMA_VERSION[0] + 5}.0"}
    with pytest.raises(ValueError, match="understands only up to"):
        migrate_to_current(raw)


def test_migrate_does_not_mutate_input():
    """migrate_to_current works on a copy; the caller's dict is untouched."""
    raw = {"additional_elements": [{"category": "image_transformer"}]}
    migrate_to_current(raw)
    assert "schema_version" not in raw
    assert raw["additional_elements"][0]["category"] == "image_transformer"


# --- the real legacy config (end-to-end) -------------------------------------


def test_full_legacy_config_migrates_every_field():
    """Every known v0->v1 transform fires on the real legacy fixture."""
    migrated, start = migrate_to_current(_load_legacy_raw())
    assert start == (0, 0)
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION_STR

    # general: local -> analysis_dir; local/remote keys removed.
    general = migrated["general"]
    assert general["analysis_dir"] == "C:/BLCA"
    assert "local_analysis_dir" not in general
    assert "remote_analysis_dir" not in general

    # core_detection -> roi_definition (+ field rename, SAM2 fields dropped).
    assert "core_detection" not in migrated
    roi_def = migrated["roi_definition"]
    assert "roi_info_file_path" in roi_def
    assert "core_info_file_path" not in roi_def
    for sam_field in ("min_area", "max_area", "min_iou", "min_st", "min_int", "frame"):
        assert sam_field not in roi_def

    # core_cutting -> roi_cutting (+ field renames).
    assert "core_cutting" not in migrated
    roi_cut = migrated["roi_cutting"]
    assert "roi_dir_tif" in roi_cut and "cores_dir_tif" not in roi_cut
    assert "roi_dir_output" in roi_cut and "cores_dir_output" not in roi_cut
    assert "roi_cleanup_enabled" in roi_cut
    assert "core_cleanup_enabled" not in roi_cut
    # channel/marker lists: blank (None) normalized to [] by v0->v1, then moved
    # from roi_cutting to channels by v1->v2
    channels = migrated["channels"]
    assert channels["include_channels"] == []
    assert channels["use_markers"] == []
    assert channels["exclude_channels"] == ["008_ECad"]
    for moved in ("include_channels", "exclude_channels", "use_markers"):
        assert moved not in roi_cut

    # additional_elements: category + ring-builder params.
    categories = [s["category"] for s in migrated["additional_elements"]]
    assert "image_filter" not in categories
    assert "image_enhancer" in categories
    ring = next(
        s for s in migrated["additional_elements"] if s.get("type") == "ring"
    )
    assert ring["parameters"]["rad_bigger"] == 8
    assert ring["parameters"]["rad_smaller"] == 2
    assert "outer" not in ring["parameters"]
    assert "inner" not in ring["parameters"]

    # quant: qc_to_layer -> qc_to_table.
    assert migrated["quant"][0].get("qc_to_table") is True
    assert "qc_to_layer" not in migrated["quant"][0]


def test_migrated_legacy_config_validates_against_schema():
    """End-to-end proof: an old file that would NOT load now loads.

    Mirrors ``load_config``'s order (migrate -> expand -> validate) and checks
    the migrated config is accepted by the current ``AnalysisConfig``.
    """
    from plex_pipe.config.config_loaders import expand_pipeline
    from plex_pipe.config.config_schema import AnalysisConfig

    migrated, _ = migrate_to_current(_load_legacy_raw())
    migrated = expand_pipeline(migrated)
    model = AnalysisConfig.model_validate(migrated)
    assert model.schema_version == CURRENT_SCHEMA_VERSION_STR
    assert model.channels.exclude_channels == ["008_ECad"]


# --- the v1 -> v2 migration (channels section) -------------------------------


def test_v1_to_v2_moves_selection_lists_to_channels():
    raw = {
        "schema_version": 1,
        "general": {"image_dir": "/im"},
        "roi_definition": {"detection_image": "x"},
        "roi_cutting": {
            "margin": 8,
            "include_channels": ["001_DAPI"],
            "exclude_channels": [],
            "use_markers": ["DAPI"],
            "ignore_markers": ["bCat"],
        },
    }
    out = migrate_v1_to_v2(raw)
    assert out["schema_version"] == "2.0"
    assert out["channels"] == {
        "include_channels": ["001_DAPI"],
        "exclude_channels": [],
        "use_markers": ["DAPI"],
        "ignore_markers": ["bCat"],
    }
    assert out["roi_cutting"] == {"margin": 8}
    # the new section is placed right after `general`
    assert list(out) == [
        "schema_version", "general", "channels", "roi_definition", "roi_cutting"
    ]


def test_v1_to_v2_moves_branch_only_keys():
    """file_naming / channel_manifest / earliest_round_markers move too."""
    raw = {
        "general": {"image_dir": "/im", "channel_manifest": "/c.csv"},
        "roi_cutting": {"earliest_round_markers": ["Hoechst"]},
    }
    out = migrate_v1_to_v2(raw)
    assert out["channels"] == {
        "earliest_round_markers": ["Hoechst"],
        "manifest": "/c.csv",
    }
    assert out["general"] == {"image_dir": "/im"}


def test_v1_to_v2_without_channel_keys_adds_no_section():
    out = migrate_v1_to_v2({"general": {"image_dir": "/im"}, "roi_cutting": {}})
    assert "channels" not in out
    assert out["schema_version"] == "2.0"


def test_v1_to_v2_is_defensive_on_new_shape():
    """Running it on 2.0-shaped input changes nothing but the stamp."""
    raw = {"general": {"image_dir": "/im"}, "channels": {"ignore_markers": ["x"]}}
    out = migrate_v1_to_v2(dict(raw))
    assert out["channels"] == {"ignore_markers": ["x"]}


def test_real_v1_config_migrates_and_validates():
    """The schema-1 example config (fixture) migrates to 2.0 and validates."""
    from plex_pipe.config.config_loaders import expand_pipeline
    from plex_pipe.config.config_schema import AnalysisConfig

    with open(V1_FIXTURE) as f:
        raw = yaml.safe_load(f)
    migrated, start = migrate_to_current(raw)
    assert start == (1, 0)
    assert migrated["schema_version"] == "2.0"
    assert migrated["channels"] == {"ignore_markers": ["bCat"]}
    assert "ignore_markers" not in migrated["roi_cutting"]

    model = AnalysisConfig.model_validate(expand_pipeline(migrated))
    assert model.channels.ignore_markers == ["bCat"]
    assert model.channels.file_naming == "celldive"


def test_unquoted_current_version_is_normalised():
    """`schema_version: 2.0` (a YAML number) is accepted and stored as "2.0"."""
    migrated, start = migrate_to_current({"schema_version": 2.0})
    assert start == (2, 0)
    assert migrated["schema_version"] == "2.0"


def test_newer_minor_loads_with_warning():
    """Same MAJOR, newer MINOR: loads, but warns that settings may be ignored."""
    from loguru import logger

    messages: list[str] = []
    handler = logger.add(lambda m: messages.append(m.record["message"]))
    try:
        migrated, start = migrate_to_current({"schema_version": "2.7"})
    finally:
        logger.remove(handler)
    assert start == (2, 7)
    assert migrated["schema_version"] == "2.7"
    assert any("newer than this build" in m for m in messages)


def test_migrate_config_writes_v2_file(tmp_path):
    """migrate_config writes `<stem>_v2.yaml` for a schema-1 file."""
    import shutil

    from plex_pipe.config.config_loaders import migrate_config

    src = tmp_path / "analysis.yaml"
    shutil.copy(V1_FIXTURE, src)
    out = migrate_config(src)
    assert out == tmp_path / "analysis_v2.yaml"
    written = yaml.safe_load(out.read_text())
    assert written["schema_version"] == "2.0"
    assert written["channels"] == {"ignore_markers": ["bCat"]}
    assert migrate_config(out) is None  # already current
