"""Tests for the mount_limits typed CRUD repository."""

from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest

from astro_brain.models.calibration import AltLimits
from astro_brain.repository.limits_repo import get_alt_limits, set_alt_limits
from astro_brain.repository.state_db import run_migrations


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an in-memory aiosqlite connection with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def test_get_returns_none_when_unset(db: aiosqlite.Connection) -> None:
    assert await get_alt_limits(db) is None


async def test_set_then_get_round_trip(db: aiosqlite.Connection) -> None:
    await set_alt_limits(db, AltLimits(min_deg=0.0, max_deg=90.0))

    result = await get_alt_limits(db)
    assert result == AltLimits(min_deg=0.0, max_deg=90.0)


async def test_second_set_overwrites(db: aiosqlite.Connection) -> None:
    await set_alt_limits(db, AltLimits(min_deg=0.0, max_deg=90.0))
    await set_alt_limits(db, AltLimits(min_deg=10.0, max_deg=80.0))

    result = await get_alt_limits(db)
    assert result == AltLimits(min_deg=10.0, max_deg=80.0)
