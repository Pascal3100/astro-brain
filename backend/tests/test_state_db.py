"""Tests for the aiosqlite repository scaffolding."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator

import aiosqlite
import pytest

from astro_brain.repository.migrations import (
    _001_initial,
    _002_alignment_model,
    _003_catalog_objects,
    _004_drop_catalog_objects,
)
from astro_brain.repository.state_db import DB_FILENAME, db_path, get_db, run_migrations


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an in-memory aiosqlite connection."""
    conn = await aiosqlite.connect(":memory:")
    try:
        yield conn
    finally:
        await conn.close()


async def _table_names(db: aiosqlite.Connection) -> set[str]:
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[0] for row in rows}


async def test_run_migrations_creates_schema(db: aiosqlite.Connection) -> None:
    version = await run_migrations(db)
    assert version == 6

    tables = await _table_names(db)
    assert {
        "schema_version",
        "calibration_sensor",
        "alignment_model",
    }.issubset(tables)
    assert "catalog_objects" not in tables
    assert "mount_limits" not in tables

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 6


async def test_run_migrations_is_idempotent(db: aiosqlite.Connection) -> None:
    first = await run_migrations(db)
    second = await run_migrations(db)
    assert first == 6
    assert second == 6

    tables = await _table_names(db)
    assert {
        "schema_version",
        "calibration_sensor",
        "alignment_model",
    }.issubset(tables)
    assert "catalog_objects" not in tables
    assert "mount_limits" not in tables

    cursor = await db.execute("SELECT COUNT(*) FROM schema_version WHERE version = 6")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 1


async def test_migration_004_drops_catalog_objects(tmp_path) -> None:
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name='catalog_objects'"
    )
    assert await cur.fetchone() is None
    await cur.close()
    cur = await conn.execute("SELECT MAX(version) FROM schema_version")
    assert (await cur.fetchone())[0] >= 4
    await cur.close()
    await conn.close()


async def test_migration_005_drops_mount_limits(tmp_path) -> None:
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name='mount_limits'"
    )
    assert await cur.fetchone() is None
    await cur.close()
    cur = await conn.execute("SELECT MAX(version) FROM schema_version")
    assert (await cur.fetchone())[0] >= 5
    await cur.close()
    await conn.close()


async def _sensor_ids(db: aiosqlite.Connection) -> set[str]:
    cursor = await db.execute("SELECT sensor_id FROM calibration_sensor")
    rows = await cursor.fetchall()
    await cursor.close()
    return {row[0] for row in rows}


async def test_migration_006_purges_retired_sensor_calibrations(
    db: aiosqlite.Connection,
) -> None:
    """Rows for retired sensors go; the live `lis3mdl` calibration stays.

    Reproduces the state found on the Pi on 2026-08-12: an `adxl345_mount`
    row left over from before the 2026-07-17 sensor retirement.
    """
    await _seed_schema_at_version_4(db)
    for sensor_id in ("adxl345_mount", "adxl345_tube", "lis3mdl"):
        await db.execute(
            "INSERT INTO calibration_sensor (sensor_id, payload_json, calibrated_at)"
            " VALUES (?, '{}', '2026-05-07T19:38:21Z')",
            (sensor_id,),
        )
    await db.commit()

    version = await run_migrations(db)

    assert version == 6
    assert await _sensor_ids(db) == {"lis3mdl"}


async def _seed_schema_at_version_4(db: aiosqlite.Connection) -> None:
    """Apply migrations _001..._004 directly, bypassing the runner.

    Used to reproduce a database that pre-dates migration _005, so the
    forward-only upgrade path can be exercised from a real VERSION 4 state.
    """
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    for module in (
        _001_initial,
        _002_alignment_model,
        _003_catalog_objects,
        _004_drop_catalog_objects,
    ):
        await db.executescript(module.SQL)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) "
            "VALUES (?, '2026-01-01T00:00:00Z')",
            (module.VERSION,),
        )
    await db.commit()


async def test_migration_005_is_forward_only_from_version_4(
    db: aiosqlite.Connection,
) -> None:
    """A DB already at VERSION 4 (with `mount_limits` present) upgrades to 5."""
    await _seed_schema_at_version_4(db)

    tables_before = await _table_names(db)
    assert "mount_limits" in tables_before
    assert "catalog_objects" not in tables_before

    version = await run_migrations(db)
    assert version == 6

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 6

    tables_after = await _table_names(db)
    assert "mount_limits" not in tables_after


def test_db_path_honors_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRO_BRAIN_STATE_DIR", str(tmp_path))
    assert db_path() == tmp_path / DB_FILENAME
    assert tmp_path.exists()


async def test_alignment_model_table_exists_after_migrations(tmp_path) -> None:
    db_file = tmp_path / "state.db"
    async with get_db(db_file) as db:
        await run_migrations(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alignment_model'"
        )
        row = await cursor.fetchone()
        await cursor.close()
    assert row is not None


async def test_alignment_model_only_one_row_allowed(tmp_path) -> None:
    db_file = tmp_path / "state.db"
    async with get_db(db_file) as db:
        await run_migrations(db)
        await db.execute(
            "INSERT INTO alignment_model (id, recorded_stars, svd_matrix, "
            "rms_arcmin, residuals, validated_at, gps_lat, gps_lon, quality) "
            "VALUES (1, '[]', '[]', 0.0, '{}', '2026-01-01T00:00:00Z', 0.0, 0.0, 'good')"
        )
        await db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO alignment_model (id, recorded_stars, svd_matrix, "
                "rms_arcmin, residuals, validated_at, gps_lat, gps_lon, quality) "
                "VALUES (2, '[]', '[]', 0.0, '{}', '2026-01-01T00:00:00Z', 0.0, 0.0, 'good')"
            )
            await db.commit()
