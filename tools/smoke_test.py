"""Release smoke test: run the whole pipeline on tiny ROIs and check the results.

Run from the repository root, in the full environment (``uv sync --extra all``):

    uv run python tools/smoke_test.py

What it does, in a fresh working folder:

1. Fetches the example images (``fetch_example``; the archive is cached).
2. Writes a ROI table with two small ROIs (``ROI_SIZE`` pixels square), so
   segmentation takes seconds instead of minutes.
3. Run A: channels from the file names (``file_naming: celldive``), the
   run-everything scripts 02 -> 04 -> 05, ``roi_cleanup_enabled: true``.
4. Run B: channels from a manifest CSV (``save_manifest``), the ``plexpipe``
   command one unit at a time (setup -> cut-image -> assemble-roi ->
   segment-roi -> quantify-roi), ``roi_cleanup_enabled: false``.
5. Checks both runs (ROI stores, tables, config snapshots, cleanup) and that
   A and B give the same tables.

Exit code 0 if every check passes, 1 otherwise. The working folder is kept
for inspection; its path is printed at the end.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import spatialdata as sd
import yaml

import plex_pipe
from plex_pipe._quiet import quiet_zarr_io

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = REPO / "examples" / "example_pipeline_config.yaml"
SCRIPTS = REPO / "scripts"

#: Side length of the square test ROIs, in pixels (full resolution).
ROI_SIZE = 512

#: Top-left corners (row, column) of the test ROIs in the example images,
#: placed in areas with tissue (inside the example's two cores).
ROI_CORNERS = {"ROI_000": (2400, 2400), "ROI_001": (2200, 9948)}

TABLE = "instanseg_table"

failures: list[str] = []


def check(ok: bool, message: str) -> None:
    """Print one check result and remember failures."""
    print(f"  [{'PASS' if ok else 'FAIL'}] {message}")
    if not ok:
        failures.append(message)


def run(cmd: list[str]) -> None:
    """Run a command, stopping the smoke test if it fails."""
    print("  $ " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=REPO)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}.")
        sys.exit(1)


def write_roi_table(path: Path) -> None:
    """Write a ROI table with small rectangular ROIs."""
    rows = []
    for name, (r0, c0) in ROI_CORNERS.items():
        r1, c1 = r0 + ROI_SIZE, c0 + ROI_SIZE
        rows.append(
            {
                "roi_name": name,
                "row_start": float(r0),
                "row_stop": float(r1),
                "column_start": float(c0),
                "column_stop": float(c1),
                "poly_type": "rectangle",
                "polygon_vertices": np.array(
                    [[r0, c1], [r1, c1], [r1, c0], [r0, c0]], dtype=float
                ),
            }
        )
    pd.DataFrame(rows).to_pickle(path)


def write_config(
    path: Path,
    image_dir: Path,
    work: Path,
    name: str,
    rois: Path,
    roi_cleanup: bool,
    manifest: Path | None = None,
) -> Path:
    """Write a copy of the example config with absolute paths for one run."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    raw["general"]["image_dir"] = str(image_dir)
    raw["general"]["analysis_dir"] = str(work)
    raw["general"]["analysis_name"] = name
    raw["roi_definition"]["roi_info_file_path"] = str(rois)
    raw["roi_cutting"]["roi_cleanup_enabled"] = roi_cleanup
    if manifest is not None:
        channels = raw.get("channels") or {}
        channels.pop("file_naming", None)
        channels["manifest"] = str(manifest)
        raw["channels"] = channels
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path


def run_a(config: Path) -> None:
    """Run A: the run-everything scripts."""
    for script in ("02_cut_rois.py", "04_segment.py", "05_quantify.py"):
        run([sys.executable, SCRIPTS / script, "--exp_config", config])


def run_b(config: Path, out_dir: Path) -> None:
    """Run B: the plexpipe command, one channel image or one ROI per call."""
    plexpipe = [sys.executable, "-m", "plex_pipe"]
    run([*plexpipe, "setup", "--exp_config", config, "--out_dir", out_dir])
    images = pd.read_csv(out_dir / "images.csv")
    for _, row in images.iterrows():
        run(
            [
                *plexpipe,
                "cut-image",
                "--exp_config",
                config,
                "--channel",
                row["channel"],
                "--image_path",
                row["path"],
            ]
        )
    rois = pd.read_csv(out_dir / "rois.csv")
    for _, row in rois.iterrows():
        run(
            [
                *plexpipe,
                "assemble-roi",
                "--exp_config",
                config,
                "--roi",
                row["roi_name"],
                "--images",
                out_dir / "images.csv",
            ]
        )
        run(
            [
                *plexpipe,
                "segment-roi",
                "--exp_config",
                config,
                "--roi_path",
                row["path"],
            ]
        )
        run(
            [
                *plexpipe,
                "quantify-roi",
                "--exp_config",
                config,
                "--roi_path",
                row["path"],
            ]
        )


def check_run(label: str, analysis: Path, roi_cleanup: bool) -> dict:
    """Check one run's outputs; return its tables by ROI name."""
    print(f"\nChecks for run {label} ({analysis.name}):")
    tables = {}
    for roi in ROI_CORNERS:
        store = analysis / "rois" / f"{roi}.zarr"
        check(store.exists(), f"{roi}: ROI store exists")
        if not store.exists():
            continue
        with quiet_zarr_io():
            sdata = sd.read_zarr(store)
        table = sdata.tables.get(TABLE)
        check(table is not None and table.n_obs > 0, f"{roi}: '{TABLE}' has cells")
        if table is not None:
            tables[roi] = table
            print(f"         {table.n_obs} cells, {table.n_vars} channels")
        tiffs = list((analysis / "temp" / roi).glob("*.tiff"))
        if roi_cleanup:
            check(not tiffs, f"{roi}: per-ROI TIFFs deleted (roi_cleanup on)")
        else:
            check(bool(tiffs), f"{roi}: per-ROI TIFFs kept (roi_cleanup off)")
    snapshots = list((analysis / "configs").glob("config_*.yaml"))
    check(len(snapshots) == 1, f"one config snapshot written ({len(snapshots)} found)")
    return tables


def compare(tables_a: dict, tables_b: dict) -> None:
    """Check that runs A and B produced the same tables."""
    print("\nRun A vs run B:")
    for roi in ROI_CORNERS:
        a, b = tables_a.get(roi), tables_b.get(roi)
        if a is None or b is None:
            check(False, f"{roi}: table missing in one of the runs")
            continue
        check(list(a.var_names) == list(b.var_names), f"{roi}: same channels")
        check(
            a.n_obs == b.n_obs, f"{roi}: same number of cells ({a.n_obs} vs {b.n_obs})"
        )
        if a.n_obs == b.n_obs and list(a.var_names) == list(b.var_names):
            xa = np.asarray(a.X.toarray() if hasattr(a.X, "toarray") else a.X)
            xb = np.asarray(b.X.toarray() if hasattr(b.X, "toarray") else b.X)
            check(np.allclose(xa, xb, equal_nan=True), f"{roi}: same intensity values")


def main() -> None:
    """Run the smoke test."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workdir",
        type=Path,
        help="Working folder (default: a new temporary folder). Must be empty.",
    )
    args = parser.parse_args()

    work = args.workdir or Path(tempfile.mkdtemp(prefix="plexpipe_smoke_"))
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        sys.exit(f"Working folder is not empty: {work}")

    print(f"PlexPipe {plex_pipe.__version__} smoke test in {work}\n")

    print("Preparing inputs:")
    image_dir = plex_pipe.fetch_example(dest=work / "images")
    rois = work / "rois.pkl"
    write_roi_table(rois)
    print(f"  {len(ROI_CORNERS)} ROIs of {ROI_SIZE} x {ROI_SIZE} px in {rois}")

    # Run A: file-name preset, scripts, ROI cleanup on.
    print("\nRun A: file names (celldive preset), scripts 02 -> 04 -> 05")
    config_a = write_config(
        work / "config_a.yaml", image_dir, work, "run_a", rois, roi_cleanup=True
    )
    run_a(config_a)

    # Run B: manifest CSV, plexpipe command, ROI cleanup off.
    print("\nRun B: channel manifest CSV, plexpipe command")
    manifest = work / "channels.csv"
    config_b = write_config(
        work / "config_b.yaml",
        image_dir,
        work,
        "run_b",
        rois,
        roi_cleanup=False,
        manifest=manifest,
    )
    plex_pipe.save_manifest(plex_pipe.load_config(config_b))
    print(f"  manifest written: {manifest}")
    run_b(config_b, work / "run_b_units")

    tables_a = check_run("A", work / "run_a", roi_cleanup=True)
    tables_b = check_run("B", work / "run_b", roi_cleanup=False)
    compare(tables_a, tables_b)

    print()
    if failures:
        print(f"SMOKE TEST FAILED: {len(failures)} check(s) failed.")
    else:
        print("SMOKE TEST PASSED.")
    print(f"Outputs kept in {work} (delete the folder when done).")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
