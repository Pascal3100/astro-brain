import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.sources.comets import comet_objects, load_comets


def _meta() -> BuildMeta:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now,
        mpc_epoch=None,
        window_start=now,
        window_end=now,
        skyfield_kernel="de421.bsp",
    )


def test_build_db_comets_are_queryable(tmp_path: Path, kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=4)
    objects, elements = comet_objects(comets)

    out = build_reference_db(tmp_path / "reference.sqlite", objects, [], rows, elements, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == SCHEMA_VERSION
        (n_obj,) = con.execute("SELECT COUNT(*) FROM objects WHERE kind='comet'").fetchone()
        assert n_obj == 3
        (n_elem,) = con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()
        assert n_elem == 3
        (n_ephem,) = con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()
        assert n_ephem == 12  # 3 comets x 4 samples
        (orphans,) = con.execute(
            "SELECT COUNT(*) FROM ephemeris e "
            "LEFT JOIN objects o ON e.object_id = o.id WHERE o.id IS NULL"
        ).fetchone()
        assert orphans == 0
    finally:
        con.close()
