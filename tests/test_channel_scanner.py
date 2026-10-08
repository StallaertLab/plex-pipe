import os

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


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        (
            dict(include_channels=["002_CD3", "003_CD3"]),
            r"several channels of marker CD3 \(002_CD3, 003_CD3\)",
        ),
        (
            dict(include_channels=["003_CD3"], exclude_channels=["003_CD3"]),
            "003_CD3 is in both include_channels and exclude_channels",
        ),
        (
            dict(include_channels=["003_CD3"], ignore_markers=["CD3"]),
            "include_channels lists 003_CD3, but marker CD3 is in ignore_markers",
        ),
        (
            dict(include_channels=["003_CD3"], use_markers=["DAPI"]),
            "include_channels lists 003_CD3, but marker CD3 is not in use_markers",
        ),
        (
            dict(use_markers=["CD3"], ignore_markers=["CD3"]),
            "Marker CD3 is in both use_markers and ignore_markers",
        ),
    ],
)
def test_contradicting_rules_are_an_error(rules, message):
    """
    Verifies: settings that ask for and reject the same channel or marker stop
    the selection instead of one silently winning.
    """
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    with pytest.raises(ValueError, match=message):
        scan_channels_from_list(files, **rules)


def test_rules_that_do_not_contradict_are_allowed():
    """Different channels of one marker in include/exclude, and excluding a
    round of a marker in use_markers, are not conflicts."""
    files = [
        "p_001.0.4_R000_DAPI_xxx.ome.tif",
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_003.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    out = scan_channels_from_list(
        files,
        include_channels=["002_CD3"],
        exclude_channels=["003_CD3", "001_DAPI"],
        use_markers=["CD3", "DAPI"],
    )
    assert out == {"CD3": "p_002.0.4_R000_dye_CD3-01_x.ome.tif"}


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
    assert (
        "  Unused: Channel 002_CD3 <- p_002.0.4_R000_dye_CD3_x.ome.tif "
        "(superseded by 003_CD3)" in log_messages
    )


def test_no_recognised_files_raises():
    with pytest.raises(ValueError, match="No files in image_dir match the 'celldive'"):
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


# --- `use` column: manifest exclusions, rules applied on top ---


def test_use_no_removes_file_before_round_selection(log_messages):
    """
    Verifies: use=no drops a file first; "latest round" then falls back to the
    next round. The log says the rules were applied on top.
    """
    records = [
        ChannelRecord("dapi.tif", "DAPI", 1),
        ChannelRecord("cd45_r2.tif", "CD45", 2),
        ChannelRecord("cd45_r3.tif", "CD45", 3, use=False),
    ]
    out = select_channels(records)
    assert out["CD45"].file == "cd45_r2.tif"
    assert (
        "Manifest column 'use': 1 file(s) excluded by the manifest; "
        "selection rules applied on top." in log_messages
    )
    assert (
        "  Unused: Channel 003_CD45 <- cd45_r3.tif (excluded in manifest (use=no))"
        in log_messages
    )


def test_include_of_use_no_file_is_an_error():
    records = [
        ChannelRecord("cd45_r2.tif", "CD45", 2, use=False),
        ChannelRecord("cd45_r3.tif", "CD45", 3),
    ]
    with pytest.raises(
        ValueError,
        match=r"include_channels lists 002_CD45, but the manifest excludes "
        r"cd45_r2.tif \(use=no\)",
    ):
        select_channels(records, include_channels=["002_CD45"])


def test_explain_selection_non_strict_reports_use_no_conflict():
    """The preview (strict=False) reports the conflict in the reason."""
    records = [
        ChannelRecord("cd45_r2.tif", "CD45", 2, use=False),
        ChannelRecord("cd45_r3.tif", "CD45", 3),
    ]
    selected, reasons = channel_scanner.explain_selection(
        records, include_channels=["002_CD45"], strict=False
    )
    assert selected["CD45"].file == "cd45_r3.tif"
    assert reasons["cd45_r2.tif"] == (
        "excluded in manifest (use=no); conflicts with include_channels"
    )


def test_renamed_marker_keeps_two_rounds():
    """
    Documented workaround: one channel is kept per marker, so to keep two
    rounds the user gives them different marker names in the manifest.
    """
    records = [
        ChannelRecord("cd45_r2.tif", "CD45_1", 2),
        ChannelRecord("cd45_r3.tif", "CD45", 3),
    ]
    out = select_channels(records)
    assert {m: r.file for m, r in out.items()} == {
        "CD45_1": "cd45_r2.tif",
        "CD45": "cd45_r3.tif",
    }


def test_explain_selection_reasons():
    records = [
        ChannelRecord("d1.tif", "DAPI", 1),
        ChannelRecord("d2.tif", "DAPI", 2),
        ChannelRecord("c2.tif", "CD3", 2),
        ChannelRecord("c3.tif", "CD3", 3),
        ChannelRecord("k1.tif", "CK7", 1),
        ChannelRecord("b1.tif", "bCat", 1),
    ]
    _, reasons = channel_scanner.explain_selection(records, ignore_markers=["bCat"])
    assert reasons == {
        "d1.tif": "selected: earliest round",
        "d2.tif": "earliest round 001_DAPI kept",
        "c3.tif": "selected: latest round",
        "c2.tif": "superseded by 003_CD3",
        "k1.tif": "selected",
        "b1.tif": "ignore_markers",
    }


# --- preview_channels / save_manifest (step 5) ---


def _cfg(
    image_dir="/d",
    file_naming="celldive",
    channel_manifest=None,
    analysis_dir="/work/A",
    **rules,
):
    """Duck-typed config: `general.image_dir`, the `channels` section and
    `analysis_dir`. `channel_manifest` maps to `channels.manifest`."""
    from types import SimpleNamespace

    channels = dict(
        file_naming=file_naming,
        manifest=channel_manifest,
        include_channels=[],
        exclude_channels=[],
        use_markers=[],
        ignore_markers=[],
        earliest_round_markers=["DAPI"],
    )
    channels.update(rules)
    return SimpleNamespace(
        general=SimpleNamespace(image_dir=image_dir),
        channels=SimpleNamespace(**channels),
        analysis_dir=analysis_dir,
    )


CELLDIVE_FILES = [
    "/d/p_001.0.4_R000_DAPI_x.ome.tif",
    "/d/p_002.0.4_R000_dye_CD3_x.ome.tif",
    "/d/p_003.0.4_R000_dye_CD3_x.ome.tif",
]


def test_preview_preset_mode_rows_and_reasons(local_listing):
    local_listing(CELLDIVE_FILES + ["/d/overview.tif"])
    table = channel_scanner.preview_channels(_cfg())
    assert list(table.columns) == [
        "file", "marker", "round", "use", "channel", "selected", "reason"
    ]
    rows = table[["file", "selected", "reason"]].values.tolist()
    assert rows == [
        ["p_001.0.4_R000_DAPI_x.ome.tif", True, "selected"],
        ["p_002.0.4_R000_dye_CD3_x.ome.tif", False, "superseded by 003_CD3"],
        ["p_003.0.4_R000_dye_CD3_x.ome.tif", True, "selected: latest round"],
        ["overview.tif", False, "not recognised by naming preset 'celldive'"],
    ]


def test_preview_reports_duplicates_instead_of_failing(local_listing):
    """A run raises on duplicate channels; the preview shows them as rows."""
    dup = [
        "/d/p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "/d/p_002.0.4_R000_dye_CD3-02_x.ome.tif",
    ]
    local_listing(["/d/p_001.0.4_R000_DAPI_x.ome.tif"] + dup)
    table = channel_scanner.preview_channels(_cfg())
    dups = table[table["reason"].str.startswith("duplicate channel 002_CD3")]
    assert len(dups) == 2 and not dups["selected"].any()
    assert table.loc[table["marker"] == "DAPI", "selected"].item()


def test_preview_manifest_mode_reports_problems(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round,use\n"
        "slide1_cycle1_Hoechst.tif,DAPI,1,\n"
        "slide1_cycle2_CD45.tif,CD45,2,\n"
        "slide1_cycle3_CD45.tif,CD45,3,no\n"
        "gone.tif,CD8,1,\n",
    )
    table = channel_scanner.preview_channels(_cfg(channel_manifest=manifest))
    reason = dict(zip(table["file"], table["reason"]))
    assert reason["slide1_cycle2_CD45.tif"] == "selected"
    assert reason["slide1_cycle3_CD45.tif"] == "excluded in manifest (use=no)"
    assert reason["gone.tif"] == "missing from image_dir"
    assert reason["overview.tif"] == "not in manifest"


@pytest.mark.parametrize("use_manifest", [False, True])
def test_preview_selects_exactly_what_discovery_selects(
    tmp_path, local_listing, use_manifest
):
    """The preview and the real run share the rules, so they must agree."""
    local_listing(CELLDIVE_FILES)
    rules = dict(exclude_channels=["003_CD3"])
    manifest = None
    if use_manifest:
        manifest = _manifest(
            tmp_path,
            "file,marker,round,use\n"
            "p_001.0.4_R000_DAPI_x.ome.tif,DAPI,1,\n"
            "p_002.0.4_R000_dye_CD3_x.ome.tif,CD3,2,\n"
            "p_003.0.4_R000_dye_CD3_x.ome.tif,CD3,3,\n",
        )
    table = channel_scanner.preview_channels(_cfg(channel_manifest=manifest, **rules))
    run = channel_scanner.discover_channels(
        "/d", channel_manifest=manifest, **rules
    )
    previewed = set(table.loc[table["selected"], "file"])
    assert previewed == {os.path.basename(p) for p in run.values()}


def test_preview_preset_argument_ignores_configured_manifest(local_listing):
    local_listing(CELLDIVE_FILES)
    cfg = _cfg(file_naming=None, channel_manifest="/does/not/matter.csv")
    table = channel_scanner.preview_channels(cfg, preset="celldive")
    assert table["selected"].sum() == 2


def test_preview_over_globus(monkeypatch):
    remote = ["/remote/s1/p_001.0.4_R000_DAPI_x.ome.tif"]
    monkeypatch.setattr(channel_scanner, "list_globus_tifs", lambda gc, p: remote)
    table = channel_scanner.preview_channels(_cfg(image_dir="/remote/s1"), gc=object())
    assert table["file"].tolist() == ["p_001.0.4_R000_DAPI_x.ome.tif"]


def test_preview_empty_image_dir(local_listing):
    local_listing([])
    with pytest.raises(ValueError, match="No TIFF files"):
        channel_scanner.preview_channels(_cfg())


def test_save_manifest_writes_inventory_only(tmp_path, local_listing):
    """
    Verifies: only file, marker, round, use are saved; `use` stays blank (the
    rules' choice is not frozen into the file); unrecognised files become
    blank rows.
    """
    local_listing(CELLDIVE_FILES + ["/d/overview.tif"])
    out = channel_scanner.save_manifest(_cfg(), tmp_path / "channels.csv")
    assert out.read_text().splitlines() == [
        "file,marker,round,use",
        "p_001.0.4_R000_DAPI_x.ome.tif,DAPI,1,",
        "p_002.0.4_R000_dye_CD3_x.ome.tif,CD3,2,",
        "p_003.0.4_R000_dye_CD3_x.ome.tif,CD3,3,",
        "overview.tif,,,",
    ]


def test_save_manifest_keeps_deliberate_no_and_drops_missing(
    tmp_path, local_listing, log_messages
):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round,use\n"
        "slide1_cycle1_Hoechst.tif,DAPI,1,\n"
        "slide1_cycle3_CD45.tif,CD45,3,no\n"
        "gone.tif,CD8,1,\n",
    )
    out = channel_scanner.save_manifest(
        _cfg(channel_manifest=manifest), tmp_path / "v2.csv"
    )
    text = out.read_text()
    assert "slide1_cycle3_CD45.tif,CD45,3,no" in text
    assert "gone.tif" not in text
    assert any("missing from image_dir" in m for m in log_messages)


def test_save_manifest_refuses_to_overwrite(tmp_path, local_listing):
    local_listing(CELLDIVE_FILES)
    out = tmp_path / "channels.csv"
    out.write_text("file,marker\nmy_edit.tif,CD3\n")
    with pytest.raises(FileExistsError):
        channel_scanner.save_manifest(_cfg(), out)
    assert out.read_text() == "file,marker\nmy_edit.tif,CD3\n"  # untouched
    channel_scanner.save_manifest(_cfg(), out, overwrite=True)
    assert out.read_text().startswith("file,marker,round,use\n")


def test_saved_manifest_reproduces_preset_run(tmp_path, local_listing):
    """Round trip: preview -> save -> manifest mode == preset mode."""
    local_listing(CELLDIVE_FILES)
    out = channel_scanner.save_manifest(_cfg(), tmp_path / "channels.csv")
    via_preset = channel_scanner.discover_channels("/d")
    via_manifest = channel_scanner.discover_channels("/d", channel_manifest=str(out))
    assert via_manifest == via_preset


def test_save_manifest_with_preset_and_globus(tmp_path, monkeypatch):
    """`preset=` and `gc=` are passed through to the listing and the parser."""
    remote = ["/remote/s1/p_001.0.4_R000_DAPI_x.ome.tif"]
    monkeypatch.setattr(channel_scanner, "list_globus_tifs", lambda gc, p: remote)
    cfg = _cfg(image_dir="/remote/s1", file_naming=None, channel_manifest="/x.csv")
    out = channel_scanner.save_manifest(
        cfg, tmp_path / "m.csv", gc=object(), preset="celldive"
    )
    assert out.read_text().splitlines()[1] == "p_001.0.4_R000_DAPI_x.ome.tif,DAPI,1,"


def test_save_manifest_defaults_to_channels_csv_in_analysis_dir(
    tmp_path, local_listing, log_messages
):
    local_listing(CELLDIVE_FILES)
    out = channel_scanner.save_manifest(_cfg(analysis_dir=tmp_path / "A"))
    assert out == tmp_path / "A" / "channels.csv"
    assert out.read_text().startswith("file,marker,round,use\n")
    assert (
        f"To use it, set manifest: {out} under channels: in your config "
        "YAML file (and remove file_naming), then reload the config." in log_messages
    )


# --- starting without Cell DIVE names and without a CSV (option C + clearer errors) ---


def test_preset_mismatch_error_points_to_manifest(local_listing):
    local_listing(NON_CELLDIVE_FILES)
    with pytest.raises(ValueError, match="plex_pipe.save_manifest\\(config\\)"):
        channel_scanner.discover_channels("/data/slide1")


def test_discover_empty_image_dir(local_listing):
    local_listing([])
    with pytest.raises(ValueError, match="No TIFF files found in image_dir: /d"):
        channel_scanner.discover_channels("/d")


def test_missing_manifest_fails_before_listing(tmp_path, monkeypatch):
    """No listing (and so no Globus call) happens before the missing CSV is reported."""

    def boom(*args):
        raise AssertionError("listing should not happen")

    monkeypatch.setattr(channel_scanner, "list_local_files", boom)
    missing = tmp_path / "channels.csv"
    with pytest.raises(FileNotFoundError, match="save_manifest"):
        channel_scanner.discover_channels("/d", channel_manifest=str(missing))


def test_preview_with_manifest_not_created_yet(tmp_path, local_listing, log_messages):
    local_listing(NON_CELLDIVE_FILES)
    cfg = _cfg(file_naming=None, channel_manifest=str(tmp_path / "channels.csv"))
    table = channel_scanner.preview_channels(cfg)
    assert len(table) == len(NON_CELLDIVE_FILES)
    assert not table["selected"].any()
    assert set(table["reason"]) == {"channel manifest not created yet"}
    assert any("does not exist yet" in m for m in log_messages)


def test_save_manifest_writes_to_configured_path_when_missing(
    tmp_path, local_listing, log_messages
):
    """
    Not Cell DIVE, no CSV yet: the config points at the future CSV and
    save_manifest(config) writes the template exactly there.
    """
    local_listing(NON_CELLDIVE_FILES)
    target = tmp_path / "manifests" / "channels.csv"
    cfg = _cfg(file_naming=None, channel_manifest=str(target))
    out = channel_scanner.save_manifest(cfg)
    assert out == target
    assert out.read_text().splitlines() == [
        "file,marker,round,use",
        "overview.tif,,,",
        "slide1_cycle1_Hoechst.tif,,,",
        "slide1_cycle2_CD45.tif,,,",
        "slide1_cycle3_CD45.tif,,,",
    ]
    assert any("already points to" in m for m in log_messages)
    # save_manifest is creating the file, so no "does not exist yet" warning
    assert not any("does not exist yet" in m for m in log_messages)


def test_save_manifest_never_overwrites_configured_manifest(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    target = tmp_path / "channels.csv"
    target.write_text("file,marker\nslide1_cycle1_Hoechst.tif,DAPI\n")
    cfg = _cfg(file_naming=None, channel_manifest=str(target))
    with pytest.raises(FileExistsError, match="it is the manifest set under channels: in your config"):
        channel_scanner.save_manifest(cfg)
    assert target.read_text() == "file,marker\nslide1_cycle1_Hoechst.tif,DAPI\n"


def test_save_manifest_logs_where_markers_came_from(tmp_path, local_listing, log_messages):
    """A new CSV is pre-filled from Cell DIVE names, and the log says so."""
    local_listing(CELLDIVE_FILES)
    target = tmp_path / "channels.csv"
    cfg = _cfg(file_naming=None, channel_manifest=str(target))
    channel_scanner.save_manifest(cfg)
    assert (
        f"Wrote channel manifest {target}: 3 files with a marker "
        "(read from file names using the 'celldive' naming), 0 left blank."
        in log_messages
    )


# --- earliest_round_markers: which markers keep their earliest round ---

NUCLEAR_ROUNDS = [
    ChannelRecord("h1.tif", "Hoechst", 1),
    ChannelRecord("h2.tif", "Hoechst", 2),
    ChannelRecord("c1.tif", "CD45", 1),
    ChannelRecord("c2.tif", "CD45", 2),
]


def test_earliest_round_markers_keeps_real_marker_name():
    """A Hoechst channel can keep its own name and still get the earliest round."""
    out = select_channels(NUCLEAR_ROUNDS, earliest_round_markers=["Hoechst"])
    assert {m: r.file for m, r in out.items()} == {
        "Hoechst": "h1.tif",
        "CD45": "c2.tif",
    }


def test_default_earliest_round_markers_is_dapi():
    """Not configured -> only DAPI keeps its earliest round (Cell DIVE default)."""
    out = select_channels(NUCLEAR_ROUNDS)
    assert out["Hoechst"].file == "h2.tif"  # latest: not in the default list


def test_empty_earliest_round_markers_keeps_latest_everywhere():
    records = [ChannelRecord("d1.tif", "DAPI", 1), ChannelRecord("d2.tif", "DAPI", 2)]
    out = select_channels(records, earliest_round_markers=[])
    assert out["DAPI"].file == "d2.tif"


def test_earliest_round_markers_case_insensitive_and_name_kept():
    """Matching ignores case; the marker keeps the name written in the manifest."""
    records = [ChannelRecord("d1.tif", "dapi", 1), ChannelRecord("d2.tif", "dapi", 2)]
    out = select_channels(records, earliest_round_markers=["DAPI"])
    assert list(out) == ["dapi"] and out["dapi"].file == "d1.tif"


def test_preview_uses_configured_earliest_round_markers(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round\n"
        "slide1_cycle1_Hoechst.tif,Hoechst,1\n"
        "slide1_cycle2_CD45.tif,Hoechst,2\n",
    )
    cfg = _cfg(
        file_naming=None, channel_manifest=manifest, earliest_round_markers=["Hoechst"]
    )
    table = channel_scanner.preview_channels(cfg)
    reason = dict(zip(table["file"], table["reason"]))
    assert reason["slide1_cycle1_Hoechst.tif"] == "selected: earliest round"
    assert reason["slide1_cycle2_CD45.tif"] == "earliest round 001_Hoechst kept"


def test_discover_passes_earliest_round_markers(tmp_path, local_listing):
    local_listing(NON_CELLDIVE_FILES)
    manifest = _manifest(
        tmp_path,
        "file,marker,round\n"
        "slide1_cycle1_Hoechst.tif,Hoechst,1\n"
        "slide1_cycle2_CD45.tif,Hoechst,2\n",
    )
    out = channel_scanner.discover_channels(
        "/data/slide1", channel_manifest=manifest, earliest_round_markers=["Hoechst"]
    )
    assert out == {"Hoechst": "/data/slide1/slide1_cycle1_Hoechst.tif"}
