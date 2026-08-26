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
    assert version == 8

    tables = await _table_names(db)
    assert {
        "schema_version",
        "alignment_model",
        "observing_site",
    }.issubset(tables)
    assert "catalog_objects" not in tables
    assert "mount_limits" not in tables
    assert "calibration_sensor" not in tables

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 8


async def test_run_migrations_is_idempotent(db: aiosqlite.Connection) -> None:
    first = await run_migrations(db)
    second = await run_migrations(db)
    assert first == 8
    assert second == 8

    tables = await _table_names(db)
    assert {
        "schema_version",
        "alignment_model",
        "observing_site",
    }.issubset(tables)
    assert "catalog_objects" not in tables
    assert "mount_limits" not in tables
    assert "calibration_sensor" not in tables

    cursor = await db.execute("SELECT COUNT(*) FROM schema_version WHERE version = 8")
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


async def test_migration_007_creates_observing_site_singleton(
    db: aiosqlite.Connection,
) -> None:
    """La table existe et le `CHECK (id = 1)` interdit une seconde ligne."""
    await run_migrations(db)

    tables = await _table_names(db)
    assert "observing_site" in tables

    await db.execute(
        "INSERT INTO observing_site (id, lat, lon, set_at) "
        "VALUES (1, 43.6, 1.44, '2026-08-26T20:00:00+00:00')"
    )
    await db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        await db.execute(
            "INSERT INTO observing_site (id, lat, lon, set_at) "
            "VALUES (2, 48.85, 2.35, '2026-08-26T20:00:00+00:00')"
        )
        await db.commit()


async def test_migration_008_drops_calibration(
    db: aiosqlite.Connection,
) -> None:
    """Plus de compass LIS3MDL (ADR 2026-08-26) → plus rien à calibrer."""
    await run_migrations(db)
    assert "calibration_sensor" not in await _table_names(db)


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
    assert version == 8

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 8

    tables_after = await _table_names(db)
    assert "mount_limits" not in tables_after


async def test_migration_008_drops_calibration_from_version_4(
    db: aiosqlite.Connection,
) -> None:
    """Une base réelle en version 4 monte jusqu'à 8 et perd sa calibration.

    La purge des capteurs retirés de _006 est devenue sans objet — la table
    entière part en _008 — mais la migration reste appliquée telle quelle
    (forward-only, les migrations posées sont immuables).
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

    assert version == 8
    assert "calibration_sensor" not in await _table_names(db)


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
