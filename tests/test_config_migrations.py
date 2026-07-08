"""Tests for schema versioning and the config migration chain."""

from pathlib import Path

import pytest
import yaml

from plex_pipe.config.config_migrations import (
    CURRENT_SCHEMA_VERSION,
    LEGACY_VERSION,
    _detect_version,
    migrate_to_current,
    migrate_v0_to_v1,
    needs_migration,
)

LEGACY_FIXTURE = Path(__file__).parent / "example_data" / "legacy_config_v0.yaml"


def _load_legacy_raw():
    """Read the real legacy (v0) config fixture as a raw dict."""
    with open(LEGACY_FIXTURE) as f:
        return yaml.safe_load(f)


# --- version detection -------------------------------------------------------


def test_absent_schema_version_is_legacy():
    """A config with no schema_version key is treated as legacy (v0)."""
    assert _detect_version({}) == LEGACY_VERSION == 0


def test_present_schema_version_is_read():
    """An explicit integer schema_version is read back as-is."""
    assert _detect_version({"schema_version": 1}) == 1


@pytest.mark.parametrize("bad", ["1", 1.0, True, None])
def test_non_integer_schema_version_raises(bad):
    """Non-integer schema_version (incl. bool/float/str) is rejected clearly."""
    with pytest.raises(ValueError, match="must be an integer"):
        _detect_version({"schema_version": bad})


def test_needs_migration():
    """needs_migration is True below current, False at current."""
    assert needs_migration(0) is True
    assert needs_migration(CURRENT_SCHEMA_VERSION) is False


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
    assert start == 0
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert migrated["additional_elements"][0]["category"] == "image_enhancer"


def test_already_current_is_unchanged():
    """A config already at the current version passes through untouched."""
    raw = {"schema_version": CURRENT_SCHEMA_VERSION, "additional_elements": []}
    migrated, start = migrate_to_current(raw)
    assert start == CURRENT_SCHEMA_VERSION
    assert migrated == raw


def test_future_version_raises_clear_error():
    """A config newer than this build understands raises a readable error."""
    raw = {"schema_version": CURRENT_SCHEMA_VERSION + 5}
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
    assert start == 0
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION

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
    # blank channel/marker lists (None) normalized to [] for clean output
    assert roi_cut["include_channels"] == []
    assert roi_cut["use_markers"] == []
    assert roi_cut["exclude_channels"] == ["008_ECad"]

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
    assert model.schema_version == CURRENT_SCHEMA_VERSION
