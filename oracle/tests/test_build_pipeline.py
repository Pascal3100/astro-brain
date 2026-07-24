import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build


def test_full_pipeline_offline(tmp_path: Path, monkeypatch) -> None:
    # force the fallback path by pointing the fetcher's dest at a copy,
    # and running with fetch=False (uses bundled fallback directly).
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    sqlite_path, manifest_path = build(
        tmp_path,
        start,
        days=3,
        sqlite_url="https://example/reference.sqlite",
        fetch=False,
    )
    assert sqlite_path.exists() and manifest_path.exists()
    con = sqlite3.connect(sqlite_path)
    try:
        (n,) = con.execute("SELECT COUNT(*) FROM comet_ephemeris").fetchone()
        assert n > 0
    finally:
        con.close()
