"""End-to-end reference build pipeline."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import oracle
from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.manifest import write_manifest
from oracle.sources.comets import fetch_comet_els, load_comets


def build(
    out_dir: Path,
    start_utc: datetime,
    *,
    days: int = 60,
    sqlite_url: str,
    fetch: bool = True,
) -> tuple[Path, Path]:
    """Run fetch→load→compute→build_db→manifest and return (sqlite_path, manifest_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    els_path = out_dir / "CometEls.txt"
    if fetch:
        fetch_comet_els(els_path)
    else:
        shutil.copyfile(oracle.data_dir() / "CometEls.fallback.txt", els_path)

    comets = load_comets(els_path)
    kernel_path = oracle.data_dir() / "de421.bsp"
    rows = compute_ephemeris(comets, kernel_path, start_utc, days=days)

    now_iso = start_utc.isoformat().replace("+00:00", "Z")
    end_iso = (start_utc + timedelta(days=days)).isoformat().replace("+00:00", "Z")
    meta = BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now_iso,
        mpc_epoch=None,
        window_start=now_iso,
        window_end=end_iso,
        skyfield_kernel="de421.bsp",
    )
    sqlite_path = build_reference_db(out_dir / "reference.sqlite", comets, rows, meta)
    manifest_path = out_dir / "manifest.json"
    write_manifest(sqlite_path, manifest_path, meta, sqlite_url)
    return sqlite_path, manifest_path
