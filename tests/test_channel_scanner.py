import pytest
from loguru import logger

import plex_pipe.stages.roi_preparation.channel_scanner as channel_scanner
from plex_pipe.stages.roi_preparation.channel_manifest import ChannelRecord
from plex_pipe.stages.roi_preparation.channel_scanner import (
    scan_channels_from_list,
    select_channels,
)


def test_scan_picks_latest_per_marker_and_prefers_001_dapi():
    """
    Verifies: channel parsing + selection policy.
    - Latest round is chosen for non-DAPI markers.
    - DAPI is normalized to key "DAPI" and prefers 001_DAPI when available.
    Why: Ensures deterministic channel set used downstream for cutting/quant.
    """
    files = [
        "p_001.0.4_R000_DAPI_x.ome.tif",
        "p_002.0.4_R000_dye_CD3_x.ome.tif",
        "p_003.0.4_R000_dye_CD3_x.ome.tif",
        "p_004.0.4_R000_dye_CK7_x.ome.tif",
        "p_004.0.4_R000_DAPI_x.ome.tif",
    ]
    out = scan_channels_from_list(files)
    assert out.keys() == {"DAPI", "CD3", "CK7"}
    # latest round for CD3 is kept
    assert out["CD3"] == "p_003.0.4_R000_dye_CD3_x.ome.tif"
    # DAPI key is normalized
    assert out["DAPI"] == "p_001.0.4_R000_DAPI_x.ome.tif"


def test_scan_include_channels_overrides_grouping():
    """
    Verifies: explicit include list bypasses grouping and keeps the exact
    channel IDs requested.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    # include exact channel name "003_CD3" to keep that one verbatim
    out = scan_channels_from_list(files, include_channels=["002_CD3"])
    assert out["CD3"] == "p_002.0.4_R000_dye_CD3-01_x.ome.tif"


def test_scan_exclude_channels_overrides_grouping():
    """
    Verifies: explicit exclude list bypasses grouping.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    # include exact channel name "003_CD3" to keep that one verbatim
    out = scan_channels_from_list(files, exclude_channels=["003_CD3"])
    assert out["CD3"] == "p_002.0.4_R000_dye_CD3-01_x.ome.tif"


def test_scan_include_exclude_channels_overrides_grouping():
    """
    Verifies: includes overwrite excludes.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    # include exact channel name "003_CD3" to keep that one verbatim
    out = scan_channels_from_list(
        files, exclude_channels=["003_CD3"], include_channels=["003_CD3"]
    )
    assert out["CD3"] == "p_003.0.4_R000_dye_CD3-02_x.ome.tif"


def test_scan_ignore_markers_overrides_grouping():
    """
    Verifies: includes overwrite excludes.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    # include exact channel name "003_CD3" to keep that one verbatim
    out = scan_channels_from_list(files, ignore_markers=["CD3"])
    assert "CD3" not in out


def test_scan_use_markers_overrides_grouping():
    """
    Verifies: includes overwrite excludes.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    # include exact channel name "003_CD3" to keep that one verbatim
    out = scan_channels_from_list(files, use_markers=["DAPI"])
    assert "CD3" not in out


def test_discover_channels_uses_globus_listing(monkeypatch):
    calls = {}

    def fake_list_globus(*args, **kwargs):
        calls["hit"] = True
        return [
            "p_001.0.4_R000_DAPI_xxx.ome.tif",
            "p_002.0.4_R000 dye CK7-01.ome.tif".replace(" ", "_"),
        ]

    # Patch the **local binding** inside channel_scanner
    monkeypatch.setattr(channel_scanner, "list_globus_tifs", fake_list_globus)

    out = channel_scanner.discover_channels("/remote/path", gc=object())
    assert calls.get("hit")
    assert set(out) == {"DAPI", "CK7"}


# --- selection on manifest records (step 2) ---


@pytest.fixture
def log_messages():
    """Capture loguru messages emitted during a test."""
    messages: list[str] = []
    handler_id = logger.add(lambda m: messages.append(m.record["message"]))
    yield messages
    logger.remove(handler_id)


def test_select_channels_on_user_manifest_without_rounds():
    """
    Verifies: records from a user manifest (no rounds, non-Cell DIVE names)
    are selected without any file-name parsing.
    """
    records = [
        ChannelRecord("nuclei.tif", "DAPI"),
        ChannelRecord("cd45.tif", "CD45"),
    ]
    out = select_channels(records)
    assert {m: r.file for m, r in out.items()} == {
        "DAPI": "nuclei.tif",
        "CD45": "cd45.tif",
    }


def test_dapi_keeps_earliest_round_when_001_missing():
    """
    Verifies: DAPI is kept even when there is no round 001 (previously it was
    silently dropped). Earliest available round wins.
    """
    files = [
        "p_002.0.4_R000_DAPI_x.ome.tif",
        "p_004.0.4_R000_DAPI_x.ome.tif",
        "p_003.0.4_R000_dye_CD3_x.ome.tif",
    ]
    out = scan_channels_from_list(files)
    assert out["DAPI"] == "p_002.0.4_R000_DAPI_x.ome.tif"


def test_dapi_falls_back_to_next_round_when_001_excluded():
    files = [
        "p_001.0.4_R000_DAPI_x.ome.tif",
        "p_004.0.4_R000_DAPI_x.ome.tif",
    ]
    out = scan_channels_from_list(files, exclude_channels=["001_DAPI"])
    assert out["DAPI"] == "p_004.0.4_R000_DAPI_x.ome.tif"


def test_scan_returns_paths_as_listed():
    """
    Verifies: the manifest stores base names, but the channel map returns the
    full paths that were listed (local or remote).
    """
    files = [
        "/remote/slide1/p_001.0.4_R000_DAPI_x.ome.tif",
        "/remote/slide1/p_002.0.4_R000_dye_CD3_x.ome.tif",
    ]
    out = scan_channels_from_list(files)
    assert out == {"DAPI": files[0], "CD3": files[1]}


def test_unrecognised_files_are_logged(log_messages):
    files = [
        "p_001.0.4_R000_DAPI_x.ome.tif",
        "overview_thumbnail.tif",
    ]
    scan_channels_from_list(files)
    assert "Files not recognised by naming preset 'celldive' 1:" in log_messages
    assert "  Unrecognised: overview_thumbnail.tif" in log_messages


def test_selected_and_unused_logged_with_file_names(log_messages):
    files = [
        "p_001.0.4_R000_DAPI_x.ome.tif",
        "p_002.0.4_R000_dye_CD3_x.ome.tif",
        "p_003.0.4_R000_dye_CD3_x.ome.tif",
    ]
    scan_channels_from_list(files)
    assert "  Channel: CD3 (003_CD3) <- p_003.0.4_R000_dye_CD3_x.ome.tif" in log_messages
    assert "  Unused: Channel 002_CD3 <- p_002.0.4_R000_dye_CD3_x.ome.tif" in log_messages


def test_no_recognised_files_raises():
    with pytest.raises(ValueError, match="No files recognised"):
        scan_channels_from_list(["a.tif", "b.tif"])
