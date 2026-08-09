"""End-to-end unified reference build pipeline (all object families)."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import oracle
from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.compute.fixed import project_to_of_date
from oracle.compute.planets import compute_planet_ephemeris
from oracle.manifest import write_manifest
from oracle.records import FixedRow, ObjectRow
from oracle.sources.comets import comet_objects, fetch_comet_els, load_comets
from oracle.sources.deep_sky import fetch_open_ngc, load_deep_sky
from oracle.sources.stars import fetch_iau_csn, load_stars


def _fetch_or_copy(fetch: bool, fetcher, dest: Path, fallback_name: str) -> Path:
    """Fetch to ``dest`` when online, else copy the bundled fallback."""
    if fetch:
        return fetcher(dest)
    shutil.copyfile(oracle.data_dir() / fallback_name, dest)
    return dest


def build(
    out_dir: Path,
    start_utc: datetime,
    *,
    days: int = 60,
    sqlite_url: str,
    fetch: bool = True,
) -> tuple[Path, Path]:
    """Run fetch→load→compute→build_db→manifest for every family; return (sqlite, manifest)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    kernel_path = oracle.data_dir() / "de421.bsp"

    # --- fetch (3 sources; each falls back to a bundled snapshot) ---
    els_path = _fetch_or_copy(
        fetch, fetch_comet_els, out_dir / "CometEls.txt", "CometEls.fallback.txt"
    )
    ngc_path = _fetch_or_copy(
        fetch, fetch_open_ngc, out_dir / "OpenNGC.csv", "OpenNGC.fallback.csv"
    )
    csn_path = _fetch_or_copy(
        fetch, fetch_iau_csn, out_dir / "IAU-CSN.txt", "IAU-CSN.fallback.txt"
    )

    # --- load ---
    comets = load_comets(els_path)
    deep_sky = load_deep_sky(ngc_path)
    stars = load_stars(csn_path)

    # --- compute ephemeral families ---
    comet_ephem = compute_ephemeris(comets, kernel_path, start_utc, days=days)
    comet_objs, comet_elems = comet_objects(comets)
    planet_objs, planet_ephem = compute_planet_ephemeris(kernel_path, start_utc, days=days)

    # --- project fixed families to of-date at generation time ---
    fixed_points = (
        [(r.id, r.ra_deg_j2000, r.dec_deg_j2000) for r in deep_sky]
        + [(s.id, s.ra_deg_j2000, s.dec_deg_j2000) for s in stars]
    )
    projected = project_to_of_date(fixed_points, kernel_path, start_utc)

    objects: list[ObjectRow] = list(comet_objs) + list(planet_objs)
    fixed: list[FixedRow] = []
    for r in deep_sky:
        ra, dec = projected[r.id]
        objects.append(ObjectRow(id=r.id, kind="dso", name=r.name, designation=r.designation))
        fixed.append(
            FixedRow(
                object_id=r.id, ra_deg=ra, dec_deg=dec, apparent_mag=r.apparent_mag,
                object_type=r.object_type, size_arcmin=r.size_arcmin,
                constellation=r.constellation, messier=r.messier, ngc_ic=r.ngc_ic,
            )
        )
    for s in stars:
        ra, dec = projected[s.id]
        objects.append(ObjectRow(id=s.id, kind="star", name=s.name, designation=s.designation))
        fixed.append(
            FixedRow(
                object_id=s.id, ra_deg=ra, dec_deg=dec, apparent_mag=s.apparent_mag,
                object_type="star", size_arcmin=None,
                constellation=s.constellation, messier=None, ngc_ic=None,
            )
        )

    ephem = list(comet_ephem) + list(planet_ephem)

    # --- meta / write / manifest ---
    now_iso = start_utc.isoformat().replace("+00:00", "Z")
    end_iso = (start_utc + timedelta(days=days - 1)).isoformat().replace("+00:00", "Z")
    meta = BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now_iso,
        mpc_epoch=None,
        window_start=now_iso,
        window_end=end_iso,
        skyfield_kernel="de421.bsp",
    )
    sqlite_path = build_reference_db(
        out_dir / "reference.sqlite", objects, fixed, ephem, comet_elems, meta
    )
    manifest_path = out_dir / "manifest.json"
    write_manifest(sqlite_path, manifest_path, meta, sqlite_url)
    return sqlite_path, manifest_path
