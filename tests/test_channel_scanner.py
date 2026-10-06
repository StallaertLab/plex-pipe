import pytest
from loguru import logger

import plex_pipe.stages.roi_preparation.channel_scanner as channel_scanner
from plex_pipe.io.channel_manifest import ChannelRecord
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


# --- discover_channels: preset vs manifest source (step 4) ---

NON_CELLDIVE_FILES = [
    "/data/slide1/slide1_cycle1_Hoechst.tif",
    "/data/slide1/slide1_cycle2_CD45.tif",
    "/data/slide1/slide1_cycle3_CD45.tif",
    "/data/slide1/overview.tif",
]


@pytest.fixture
def local_listing(monkeypatch):
    """Patch the local directory listing used by discover_channels."""

    def _set(files):
        monkeypatch.setattr(channel_scanner, "list_local_files", lambda _dir: files)

    return _set


def _manifest(tmp_path, text):
    p = tmp_path / "channels.csv"
    p.write_text(text)
    return str(p)


def test_discover_with_manifest_uses_csv_not_file_names(tmp_path, local_listing):
    """
    Verifies: with a manifest, non-Cell DIVE file names work; markers and rounds
    come from the CSV; selection rules still apply (latest CD45 round wins).
    """
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round\n"
        "slide1_cycle1_Hoechst.tif,DAPI,1\n"
        "slide1_cycle2_CD45.tif,CD45,2\n"
        "slide1_cycle3_CD45.tif,CD45,3\n",
    )
    out = channel_scanner.discover_channels("/data/slide1", channel_manifest=manifest)
    assert out == {
        "DAPI": "/data/slide1/slide1_cycle1_Hoechst.tif",
        "CD45": "/data/slide1/slide1_cycle3_CD45.tif",
    }


def test_discover_with_manifest_applies_marker_rules(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round\n"
        "slide1_cycle1_Hoechst.tif,DAPI,1\n"
        "slide1_cycle2_CD45.tif,CD45,2\n",
    )
    out = channel_scanner.discover_channels(
        "/data/slide1", ignore_markers=["CD45"], channel_manifest=manifest
    )
    assert set(out) == {"DAPI"}


def test_manifest_file_missing_from_image_dir_raises(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(tmp_path, "file,marker\nnot_there.tif,CD3\n")
    with pytest.raises(ValueError, match="not_there.tif"):
        channel_scanner.discover_channels("/data/slide1", channel_manifest=manifest)


def test_files_not_in_manifest_are_logged(tmp_path, local_listing, log_messages):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(tmp_path, "file,marker\nslide1_cycle1_Hoechst.tif,DAPI\n")
    channel_scanner.discover_channels("/data/slide1", channel_manifest=manifest)
    assert "Files in image_dir not listed in the manifest 3:" in log_messages
    assert "  Not in manifest: overview.tif" in log_messages


def test_discover_with_manifest_over_globus_returns_remote_paths(
    tmp_path, monkeypatch
):
    remote = ["/remote/s1/a_cycle1_DAPI.tif", "/remote/s1/a_cycle1_CD3.tif"]
    monkeypatch.setattr(channel_scanner, "list_globus_tifs", lambda gc, p: remote)
    manifest = _manifest(
        tmp_path, "file,marker\na_cycle1_DAPI.tif,DAPI\na_cycle1_CD3.tif,CD3\n"
    )
    out = channel_scanner.discover_channels(
        "/remote/s1", gc=object(), channel_manifest=manifest
    )
    assert out == {"DAPI": remote[0], "CD3": remote[1]}


def test_discover_defaults_to_celldive_preset(local_listing, log_messages):
    local_listing(["/d/p_001.0.4_R000_DAPI_x.ome.tif"])
    out = channel_scanner.discover_channels("/d")
    assert out == {"DAPI": "/d/p_001.0.4_R000_DAPI_x.ome.tif"}
    assert "Channel source: naming preset 'celldive' (image_dir: /d)" in log_messages


def test_discover_unknown_preset_raises(local_listing):
    from plex_pipe.io.channel_manifest import ManifestError

    local_listing(["/d/p_001.0.4_R000_DAPI_x.ome.tif"])
    with pytest.raises(ManifestError, match="Unknown naming preset"):
        channel_scanner.discover_channels("/d", file_naming="phenocycler")
