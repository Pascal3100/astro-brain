import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build


def test_full_pipeline_offline_all_families(tmp_path: Path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    sqlite_path, manifest_path = build(
        tmp_path,
        start,
        days=3,
        sqlite_url="https://example/reference.sqlite",
        fetch=False,  # use bundled fallbacks: fully offline, deterministic
    )
    assert sqlite_path.exists() and manifest_path.exists()

    con = sqlite3.connect(sqlite_path)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == 2
        kinds = {k for (k,) in con.execute("SELECT DISTINCT kind FROM objects")}
        assert kinds == {"comet", "planet", "moon", "sun", "dso", "star"}
        # every family produced rows in its target table
        assert con.execute("SELECT COUNT(*) FROM fixed_object").fetchone()[0] > 10000
        assert con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()[0] > 0
        assert con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()[0] > 0
        # 9 ephemeral bodies from de421 present
        (n_bodies,) = con.execute(
            "SELECT COUNT(*) FROM objects WHERE kind IN ('planet','moon','sun')"
        ).fetchone()
        assert n_bodies == 9
        # Messier fully covered
        (n_messier,) = con.execute(
            "SELECT COUNT(DISTINCT messier) FROM fixed_object WHERE messier IS NOT NULL"
        ).fetchone()
        assert n_messier == 110
        # global FK integrity across all child tables
        for child in ("fixed_object", "ephemeris", "comet_elements"):
            (orphans,) = con.execute(
                f"SELECT COUNT(*) FROM {child} c "
                f"LEFT JOIN objects o ON c.object_id = o.id WHERE o.id IS NULL"
            ).fetchone()
            assert orphans == 0, child
    finally:
        con.close()
