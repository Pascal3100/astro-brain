"""Tests for the calibration_sensor typed CRUD repository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import aiosqlite
import pytest

from astro_brain.models.calibration import Lis3mdlOffsets
from astro_brain.repository.calibration_repo import (
    SENSOR_IDS,
    get_offsets,
    upsert_offsets,
)
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


def _lis3mdl_payload() -> Lis3mdlOffsets:
    return Lis3mdlOffsets(
        offsets=(1.0, 2.0, 3.0),
        scale_matrix=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        coverage_pct=85.0,
        residual=0.012,
    )


def test_sensor_ids_are_known() -> None:
    assert frozenset({"lis3mdl"}) == SENSOR_IDS


async def test_upsert_then_get_lis3mdl(db: aiosqlite.Connection) -> None:
    payload = _lis3mdl_payload()
    await upsert_offsets(db, "lis3mdl", payload)

    status = await get_offsets(db, "lis3mdl")
    assert status.sensor_id == "lis3mdl"
    assert status.payload == payload
    assert isinstance(status.calibrated_at, datetime)
    assert status.calibrated_at.tzinfo is not None


async def test_get_returns_empty_status_when_missing(db: aiosqlite.Connection) -> None:
    status = await get_offsets(db, "lis3mdl")
    assert status.sensor_id == "lis3mdl"
    assert status.payload is None
    assert status.calibrated_at is None


async def test_get_rejects_unknown_sensor_id(db: aiosqlite.Connection) -> None:
    with pytest.raises(ValueError):
        await get_offsets(db, "foo")


async def test_upsert_rejects_unknown_sensor_id(db: aiosqlite.Connection) -> None:
    payload = _lis3mdl_payload()
    with pytest.raises(ValueError):
        await upsert_offsets(db, "foo", payload)
