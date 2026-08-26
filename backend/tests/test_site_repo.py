"""Tests du repo `observing_site` (singleton id=1)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest
from pydantic import ValidationError

from astro_brain.repository import site_repo
from astro_brain.repository.state_db import run_migrations


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def test_get_site_returns_none_when_never_set(db: aiosqlite.Connection) -> None:
    assert await site_repo.get_site(db) is None


async def test_set_then_get_round_trip(db: aiosqlite.Connection) -> None:
    written = await site_repo.set_site(db, 43.6, 1.44)
    read = await site_repo.get_site(db)

    assert read is not None
    assert (read.lat, read.lon) == (43.6, 1.44)
    assert read.set_at == written.set_at


async def test_rewriting_keeps_a_single_row(db: aiosqlite.Connection) -> None:
    """Le `CHECK (id = 1)` + l'upsert garantissent le singleton."""
    first = await site_repo.set_site(db, 43.6, 1.44)
    second = await site_repo.set_site(db, 48.85, 2.35)

    cursor = await db.execute("SELECT COUNT(*) FROM observing_site")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 1

    read = await site_repo.get_site(db)
    assert read is not None
    assert (read.lat, read.lon) == (48.85, 2.35)
    assert second.set_at >= first.set_at


async def test_out_of_range_latitude_never_reaches_the_db(
    db: aiosqlite.Connection,
) -> None:
    with pytest.raises(ValidationError):
        await site_repo.set_site(db, 91.0, 1.44)

    assert await site_repo.get_site(db) is None
