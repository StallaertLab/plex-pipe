import pytest

from plex_pipe.stages.roi_preparation.channel_manifest import (
    ChannelRecord,
    ManifestError,
    build_manifest,
    parse_celldive_name,
    read_manifest,
    write_manifest,
)

# --- Cell DIVE preset: must reproduce the legacy hardcoded parser ---


@pytest.mark.parametrize(
    ("fname", "expected"),
    [
        # documented example (docs/usage/input_data.md)
        ("BLCA-1_1.0.4_R000_Cy3_pH2AX-AF555_FINAL_AFR_F.ome.tif", ("pH2AX", 1)),
        # DAPI is recognised from the dye segment, any case
        ("BLCA-1_1.0.4_R000_DAPI__FINAL_F.ome.tif", ("DAPI", 1)),
        ("p_004.0.4_R000_dapi_x.ome.tif", ("DAPI", 4)),
        ("sample_1.0.4_R000_DAPI__FINAL_F.tiff", ("DAPI", 1)),
        # marker keeps everything before the LAST hyphen
        ("p_002.0.4_R000_dye_CD3-01_x.ome.tif", ("CD3", 2)),
        ("p_002.0.4_R000_dye_CD3_x.ome.tif", ("CD3", 2)),
        ("p_002.0.4_R000_dye_A-B-C_x.ome.tif", ("A-B", 2)),
        # no "_..." part after the marker
        ("p_002.0.4_R000_dye_CK7-01.ome.tif", ("CK7", 2)),
        ("p_002.0.4_R000_dye_Ki-67-AF488.ome.tif", ("Ki-67", 2)),
        # legacy parser returned "CD3.ome.tif" here; the extension is now dropped
        ("p_002.0.4_R000_dye_CD3.ome.tif", ("CD3", 2)),
        # not Cell DIVE
        ("notes.txt", None),
        ("sample_cycle1_CD45.tif", None),
        ("BLCA_1_1.0.4_R000_Cy3_CD45-AF647_F.tif", None),  # '_' in prefix
    ],
)
def test_parse_celldive_name(fname, expected):
    assert parse_celldive_name(fname) == expected


def test_build_manifest_stores_basenames_and_reports_unmatched():
    files = [
        "/data/img/p_003.0.4_R000_dye_CD3_x.ome.tif",
        r"C:\data\img\p_001.0.4_R000_DAPI_x.ome.tif",
        "/data/img/readme.txt",
    ]
    records, unmatched = build_manifest(files, "celldive")
    assert records == [
        ChannelRecord("p_001.0.4_R000_DAPI_x.ome.tif", "DAPI", 1),
        ChannelRecord("p_003.0.4_R000_dye_CD3_x.ome.tif", "CD3", 3),
    ]
    assert unmatched == ["readme.txt"]


def test_build_manifest_rejects_duplicate_channels():
    files = [
        "p_002.0.4_R000_dye_CD3-01_x.ome.tif",
        "p_002.0.4_R000_dye_CD3-02_x.ome.tif",  # same round + marker
    ]
    with pytest.raises(ManifestError, match="002_CD3"):
        build_manifest(files, "celldive")


def test_build_manifest_unknown_preset():
    with pytest.raises(ManifestError, match="Unknown naming preset"):
        build_manifest([], "phenocycler")


def test_channel_name():
    assert ChannelRecord("f.tif", "CD3", 2).channel == "002_CD3"


# --- user-provided CSV ---


def _write(tmp_path, text, name="manifest.csv", encoding="utf-8"):
    p = tmp_path / name
    p.write_text(text, encoding=encoding)
    return p


def test_read_minimal_manifest_defaults_round(tmp_path):
    p = _write(tmp_path, "file,marker\na.tif,DAPI\nb.tif,CD45\n")
    # records come back sorted by channel name
    assert read_manifest(p) == [
        ChannelRecord("b.tif", "CD45", 1),
        ChannelRecord("a.tif", "DAPI", 1),
    ]


def test_read_manifest_excel_variants(tmp_path):
    """Semicolons, BOM, header case, whitespace, blank lines, extra columns."""
    text = "File ; Marker ; Round ; notes\n a.tif ; DAPI ; 2 ; ok\n\nb.tif;CD3;;\n"
    p = _write(tmp_path, "\ufeff" + text)
    assert read_manifest(p) == [
        ChannelRecord("b.tif", "CD3", 1),
        ChannelRecord("a.tif", "DAPI", 2),
    ]


def test_read_manifest_missing_column(tmp_path):
    p = _write(tmp_path, "file,round\na.tif,1\n")
    with pytest.raises(ManifestError, match="missing required column"):
        read_manifest(p)


def test_read_manifest_reports_every_bad_row(tmp_path):
    p = _write(tmp_path, "file,marker,round\na.tif,,1\nb.tif,CD3,two\n,CD4,1\n")
    with pytest.raises(ManifestError) as exc:
        read_manifest(p)
    msg = str(exc.value)
    assert "row 2" in msg and "row 3" in msg and "row 4" in msg


def test_read_manifest_duplicate_channel(tmp_path):
    p = _write(tmp_path, "file,marker,round\na.tif,CD3,1\nb.tif,CD3,1\n")
    with pytest.raises(ManifestError, match="001_CD3"):
        read_manifest(p)


def test_read_empty_manifest(tmp_path):
    p = _write(tmp_path, "file,marker,round\n")
    with pytest.raises(ManifestError, match="no entries"):
        read_manifest(p)


def test_write_read_roundtrip(tmp_path):
    records = [ChannelRecord("a.tif", "DAPI", 1), ChannelRecord("b.tif", "CD3", 2)]
    out = write_manifest(records, tmp_path / "sub" / "m.csv")
    lines = out.read_text().splitlines()
    assert lines == ["file,marker,round", "a.tif,DAPI,1", "b.tif,CD3,2"]
    assert sorted(read_manifest(out), key=lambda r: r.file) == records
