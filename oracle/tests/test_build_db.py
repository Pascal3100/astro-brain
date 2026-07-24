import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.sources.comets import load_comets


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


def test_build_db_is_queryable(tmp_path: Path, kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=4)

    out = build_reference_db(tmp_path / "reference.sqlite", comets, rows, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == SCHEMA_VERSION
        (n_comets,) = con.execute("SELECT COUNT(*) FROM comets").fetchone()
        assert n_comets == 3
        (n_ephem,) = con.execute("SELECT COUNT(*) FROM comet_ephemeris").fetchone()
        assert n_ephem == 12  # 3 comets x 4 samples
        # every ephemeris row references an existing comet (FK integrity)
        (orphans,) = con.execute(
            "SELECT COUNT(*) FROM comet_ephemeris e "
            "LEFT JOIN comets c ON e.comet_id = c.id WHERE c.id IS NULL"
        ).fetchone()
        assert orphans == 0
    finally:
        con.close()
