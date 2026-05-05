"""Tests for the calibration_sensor typed CRUD repository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import aiosqlite
import pytest

from astro_brain.models.calibration import (
    Adxl345Offsets,
    Lis3mdlOffsets,
)
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
    assert frozenset({"lis3mdl", "adxl345_mount", "adxl345_tube"}) == SENSOR_IDS


async def test_upsert_then_get_lis3mdl(db: aiosqlite.Connection) -> None:
    payload = _lis3mdl_payload()
    await upsert_offsets(db, "lis3mdl", payload)

    status = await get_offsets(db, "lis3mdl")
    assert status.sensor_id == "lis3mdl"
    assert status.payload == payload
    assert isinstance(status.calibrated_at, datetime)
    assert status.calibrated_at.tzinfo is not None


async def test_upsert_then_get_adxl345_mount(db: aiosqlite.Connection) -> None:
    payload = Adxl345Offsets(bias=(0.1, -0.2, 9.8), sigma=0.05)
    await upsert_offsets(db, "adxl345_mount", payload)

    status = await get_offsets(db, "adxl345_mount")
    assert status.sensor_id == "adxl345_mount"
    assert status.payload == payload
    assert isinstance(status.payload, Adxl345Offsets)
    assert status.payload.zero_alt_deg is None
    assert isinstance(status.calibrated_at, datetime)
    assert status.calibrated_at.tzinfo is not None


async def test_upsert_then_get_adxl345_tube(db: aiosqlite.Connection) -> None:
    payload = Adxl345Offsets(bias=(0.0, 0.0, 9.81), sigma=0.03, zero_alt_deg=0.0)
    await upsert_offsets(db, "adxl345_tube", payload)

    status = await get_offsets(db, "adxl345_tube")
    assert status.sensor_id == "adxl345_tube"
    assert status.payload == payload
    assert isinstance(status.payload, Adxl345Offsets)
    assert status.payload.zero_alt_deg == 0.0


async def test_get_returns_empty_status_when_missing(db: aiosqlite.Connection) -> None:
    status = await get_offsets(db, "lis3mdl")
    assert status.sensor_id == "lis3mdl"
    assert status.payload is None
    assert status.calibrated_at is None


async def test_upsert_overwrites(db: aiosqlite.Connection) -> None:
    first = Adxl345Offsets(bias=(0.1, 0.2, 9.7), sigma=0.05)
    second = Adxl345Offsets(bias=(1.0, 1.0, 9.9), sigma=0.01)

    await upsert_offsets(db, "adxl345_mount", first)
    await upsert_offsets(db, "adxl345_mount", second)

    status = await get_offsets(db, "adxl345_mount")
    assert status.payload == second


async def test_get_rejects_unknown_sensor_id(db: aiosqlite.Connection) -> None:
    with pytest.raises(ValueError):
        await get_offsets(db, "foo")


async def test_upsert_rejects_unknown_sensor_id(db: aiosqlite.Connection) -> None:
    payload = Adxl345Offsets(bias=(0.0, 0.0, 9.81), sigma=0.05)
    with pytest.raises(ValueError):
        await upsert_offsets(db, "foo", payload)


async def test_upsert_rejects_type_mismatch_lis3mdl_with_adxl_payload(
    db: aiosqlite.Connection,
) -> None:
    payload = Adxl345Offsets(bias=(0.0, 0.0, 9.81), sigma=0.05)
    with pytest.raises(TypeError):
        await upsert_offsets(db, "lis3mdl", payload)


async def test_upsert_rejects_type_mismatch_adxl_with_lis3mdl_payload(
    db: aiosqlite.Connection,
) -> None:
    payload = _lis3mdl_payload()
    with pytest.raises(TypeError):
        await upsert_offsets(db, "adxl345_mount", payload)
