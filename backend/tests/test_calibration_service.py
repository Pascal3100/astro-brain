"""Tests for CalibrationServiceImpl (state machine + sampling + persistence)."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator

import aiosqlite
import numpy as np
import pytest

from astro_brain.models.calibration import Adxl345Offsets, CalibrationProgress
from astro_brain.repository import calibration_repo
from astro_brain.repository.state_db import run_migrations
from astro_brain.services.calibration import CalibrationServiceImpl
from astro_brain.services.interfaces import ConflictError

from .fakes.sensor_fakes import FakeAdxl345 as FakeAdxl345Adapter
from .fakes.sensor_fakes import FakeLis3mdl as FakeLis3mdlAdapter

# ---------------------------------------------------------------------------
# Fixture: in-memory DB with migrations applied
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an in-memory aiosqlite connection with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMMOBILE = [(1.0, 0.0, 0.0)] * 200  # constant → sigma=0, bias=(1,0,0)
_FAST_KWARGS = {
    "sample_period_s": 0.001,
    "progress_period_s": 0.005,
    "adxl_min_samples": 100,
}


def _make_service(
    db: aiosqlite.Connection,
    *,
    adxl_samples: list[tuple[float, float, float]] | None = None,
    lis_samples: list[tuple[float, float, float]] | None = None,
    **kwargs,
) -> CalibrationServiceImpl:
    adxl_s = adxl_samples or _IMMOBILE
    lis_s = lis_samples or [(10.0, 0.0, 0.0)] * 600
    return CalibrationServiceImpl(
        db=db,
        adxl_mount=FakeAdxl345Adapter(adxl_s),
        adxl_tube=FakeAdxl345Adapter(adxl_s),
        lis3mdl=FakeLis3mdlAdapter(lis_s),
        **{**_FAST_KWARGS, **kwargs},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_start_creates_session(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("adxl345_mount")

    assert isinstance(sid, str) and len(sid) == 32
    session = await svc.current_session()
    assert session == (sid, "adxl345_mount")
    # State is sampling after start.
    assert svc._state == "sampling"

    await svc.abort(sid)


async def test_concurrent_start_raises_conflict(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("adxl345_mount")
    try:
        with pytest.raises(ConflictError):
            await svc.start("adxl345_tube")
        with pytest.raises(ConflictError):
            await svc.start("adxl345_mount")
    finally:
        await svc.abort(sid)


async def test_progress_emits_state_updates(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("adxl345_mount")

    # Let the sampling task accumulate some samples.
    await asyncio.sleep(0.05)

    yields: list[CalibrationProgress] = []
    async for p in svc.progress(sid):
        yields.append(p)
        if len(yields) >= 3:
            break

    assert len(yields) == 3
    # samples_n must be non-decreasing
    for a, b in zip(yields, yields[1:], strict=False):
        assert b.samples_n >= a.samples_n
    # state is still sampling (we didn't finalize)
    for p in yields:
        assert p.state == "sampling"

    await svc.abort(sid)


async def test_finalize_writes_to_db_and_clears_session(
    db: aiosqlite.Connection,
) -> None:
    svc = _make_service(db, adxl_samples=_IMMOBILE)
    sid = await svc.start("adxl345_mount")

    # Let sampling accumulate at least 100 samples.
    await asyncio.sleep(0.2)

    status = await svc.finalize(sid)

    # Returned status is persisted.
    assert status.sensor_id == "adxl345_mount"
    assert status.calibrated_at is not None
    assert status.payload is not None

    assert isinstance(status.payload, Adxl345Offsets)
    bias = status.payload.bias
    assert math.isclose(bias[0], 1.0, abs_tol=1e-6)
    assert math.isclose(bias[1], 0.0, abs_tol=1e-6)
    assert math.isclose(bias[2], 0.0, abs_tol=1e-6)
    assert status.payload.sigma < 1e-9  # noqa: SIM300 — sigma < 1e-9 reads intent clearly

    # Verify DB was actually written.
    db_status = await calibration_repo.get_offsets(db, "adxl345_mount")
    assert db_status.calibrated_at is not None

    # Session must be cleared.
    assert await svc.current_session() is None


async def test_abort_resets_to_idle_without_writing_db(
    db: aiosqlite.Connection,
) -> None:
    svc = _make_service(db)
    sid = await svc.start("adxl345_mount")
    await asyncio.sleep(0.02)
    await svc.abort(sid)

    # DB must remain empty.
    db_status = await calibration_repo.get_offsets(db, "adxl345_mount")
    assert db_status.calibrated_at is None
    assert db_status.payload is None

    # Session cleared.
    assert await svc.current_session() is None
    assert svc._state == "aborted"


async def test_finalize_before_threshold_raises(db: aiosqlite.Connection) -> None:
    # Only 50 samples before finalize.
    svc = _make_service(
        db,
        adxl_samples=_IMMOBILE,
        sample_period_s=0.001,
        progress_period_s=0.005,
        adxl_min_samples=100,
    )
    sid = await svc.start("adxl345_mount")
    # Sleep long enough for ~50 samples at 0.001s each, but less than 100.
    await asyncio.sleep(0.055)
    # Force only 50 samples to be in the list for a deterministic test.
    svc._samples = svc._samples[:50]

    with pytest.raises(ValueError, match="insufficient samples"):
        await svc.finalize(sid)

    # Session must be cleared after the error.
    assert await svc.current_session() is None


async def test_lis3mdl_coverage_threshold(db: aiosqlite.Connection) -> None:
    """500 hemisphere-only samples (z>0) → coverage too low → finalize raises."""
    rng = np.random.default_rng(42)
    # Generate 600 unit-sphere samples with z > 0 only.
    angles = rng.uniform(0, np.pi / 2, size=600)     # polar angle in upper hemisphere
    phi = rng.uniform(0, 2 * np.pi, size=600)
    r = 40.0  # arbitrary non-unit radius
    xs = r * np.sin(angles) * np.cos(phi)
    ys = r * np.sin(angles) * np.sin(phi)
    zs = r * np.cos(angles)
    hemi_samples: list[tuple[float, float, float]] = [
        (float(x), float(y), float(z)) for x, y, z in zip(xs, ys, zs, strict=True)
    ]

    svc = CalibrationServiceImpl(
        db=db,
        adxl_mount=FakeAdxl345Adapter(_IMMOBILE),
        adxl_tube=FakeAdxl345Adapter(_IMMOBILE),
        lis3mdl=FakeLis3mdlAdapter(hemi_samples),
        sample_period_s=0.001,
        progress_period_s=0.005,
        lis3mdl_min_samples=500,
        lis3mdl_coverage_threshold=80.0,
    )
    sid = await svc.start("lis3mdl")
    # Wait for > 500 samples (500 × 0.001s = 0.5s, plus margin).
    await asyncio.sleep(0.7)

    with pytest.raises(ValueError, match="coverage"):
        await svc.finalize(sid)

    assert await svc.current_session() is None
