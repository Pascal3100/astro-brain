"""Tests for the aiosqlite repository scaffolding."""

from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest

from astro_brain.repository.state_db import DB_FILENAME, db_path, run_migrations


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
    assert version == 1

    tables = await _table_names(db)
    assert {"schema_version", "calibration_sensor", "mount_limits"}.issubset(tables)

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 1


async def test_run_migrations_is_idempotent(db: aiosqlite.Connection) -> None:
    first = await run_migrations(db)
    second = await run_migrations(db)
    assert first == 1
    assert second == 1

    tables = await _table_names(db)
    assert {"schema_version", "calibration_sensor", "mount_limits"}.issubset(tables)

    cursor = await db.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 1


def test_db_path_honors_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRO_BRAIN_STATE_DIR", str(tmp_path))
    assert db_path() == tmp_path / DB_FILENAME
    assert tmp_path.exists()
