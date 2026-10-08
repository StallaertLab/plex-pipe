"""Tests for save_config_snapshot: one file per distinct config used."""

import re
from pathlib import Path

import pytest
import yaml
from loguru import logger

from plex_pipe.config.config_loaders import load_config, save_config_snapshot

REPO = Path(__file__).parents[1]
EXAMPLE_V2 = REPO / "examples" / "example_pipeline_config.yaml"
EXAMPLE_V1 = REPO / "tests" / "example_data" / "config_v1.yaml"


@pytest.fixture
def log_messages():
    """Capture loguru messages emitted during a test."""
    messages: list[str] = []
    handler_id = logger.add(lambda m: messages.append(m.record["message"]))
    yield messages
    logger.remove(handler_id)


def _copy_config(src: Path, tmp_path: Path) -> Path:
    """Copy a config into tmp_path, pointing analysis_dir and image_dir there."""
    raw = yaml.safe_load(src.read_text())
    raw["general"]["analysis_dir"] = str(tmp_path / "out")
    raw["general"]["image_dir"] = str(tmp_path / "images")
    out = tmp_path / src.name
    out.write_text(yaml.safe_dump(raw, sort_keys=False))
    return out


def test_snapshot_written_to_analysis_dir_and_reloads(tmp_path):
    path = _copy_config(EXAMPLE_V2, tmp_path)
    config = load_config(path)

    snap = save_config_snapshot(config)

    assert snap.parent == config.analysis_dir / "configs"
    assert re.fullmatch(r"config_[0-9a-f]{8}\.yaml", snap.name)
    text = snap.read_text()
    assert f"# from: {path.resolve()}\n" in text
    assert "# schema 2.0\n" in text
    assert "# PlexPipe: " in text
    # Nothing is written next to the source file.
    assert sorted(p.name for p in tmp_path.glob("*.yaml")) == [path.name]
    # The snapshot is a loadable config equal to the original.
    assert load_config(snap).model_dump(warnings=False) == config.model_dump(
        warnings=False
    )


def test_snapshot_records_upgrade_from_older_schema(tmp_path):
    path = _copy_config(EXAMPLE_V1, tmp_path)
    config = load_config(path)

    snap = save_config_snapshot(config)

    text = snap.read_text()
    assert "# schema 1.0 in the source file, upgraded to 2.0\n" in text
    body = yaml.safe_load(text)
    assert body["schema_version"] == "2.0"
    assert body["channels"]["ignore_markers"] == ["bCat"]
    assert "ignore_markers" not in body["roi_cutting"]


def test_snapshot_keeps_unexpanded_pipeline(tmp_path):
    """The snapshot holds the config as written, not the expanded steps."""
    path = _copy_config(EXAMPLE_V2, tmp_path)
    config = load_config(path)

    body = yaml.safe_load(save_config_snapshot(config).read_text())

    assert body == {
        **yaml.safe_load(path.read_text()),
        "schema_version": "2.0",
    }


def test_same_config_reuses_one_snapshot(tmp_path, log_messages):
    """All steps run with an unchanged config share one file."""
    path = _copy_config(EXAMPLE_V2, tmp_path)
    first = save_config_snapshot(load_config(path))
    written = first.read_text()

    second = save_config_snapshot(load_config(path))

    assert second == first
    assert first.read_text() == written  # not rewritten
    assert len(list(first.parent.iterdir())) == 1
    logged = [m for m in log_messages if m.startswith("Config snapshot:")]
    assert "(new; source " in logged[0]
    assert "(existing; source " in logged[1]


def test_changed_config_gets_a_new_snapshot(tmp_path):
    path = _copy_config(EXAMPLE_V2, tmp_path)
    first = save_config_snapshot(load_config(path))

    raw = yaml.safe_load(path.read_text())
    raw["roi_cutting"]["margin"] = 25
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    second = save_config_snapshot(load_config(path))

    assert second != first
    assert first.exists()
    assert second.exists()
    assert yaml.safe_load(second.read_text())["roi_cutting"]["margin"] == 25


def test_key_order_does_not_change_the_snapshot(tmp_path):
    """Reordering keys in the YAML file is the same config."""
    path = _copy_config(EXAMPLE_V2, tmp_path)
    first = save_config_snapshot(load_config(path))

    raw = yaml.safe_load(path.read_text())
    path.write_text(yaml.safe_dump(dict(reversed(raw.items())), sort_keys=False))

    assert save_config_snapshot(load_config(path)) == first


def test_config_not_from_file_writes_nothing(tmp_path):
    config = load_config(_copy_config(EXAMPLE_V2, tmp_path))
    rebuilt = type(config).model_validate(config.model_dump(warnings=False))

    assert save_config_snapshot(rebuilt) is None
    assert not (config.analysis_dir / "configs").exists()


def test_log_line_records_the_run(tmp_path, log_messages):
    path = _copy_config(EXAMPLE_V1, tmp_path)
    snap = save_config_snapshot(load_config(path))
    assert any(
        m.startswith(f"Config snapshot: {snap} (new; ")
        and f"source {path.resolve()}, run from {Path.cwd()}, PlexPipe " in m
        and m.endswith("schema 1.0 in the source file, upgraded to 2.0)")
        for m in log_messages
    )
