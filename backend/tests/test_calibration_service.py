"""Tests for CalibrationServiceImpl (state machine + sampling + persistence)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import aiosqlite
import numpy as np
import pytest

from astro_brain.models.calibration import CalibrationProgress, Lis3mdlOffsets
from astro_brain.repository import calibration_repo
from astro_brain.repository.state_db import run_migrations
from astro_brain.services.calibration import CalibrationServiceImpl
from astro_brain.services.interfaces import ConflictError

from ._calibration_samples import full_sphere_samples as _full_sphere_samples
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


def _hemisphere_samples(n: int, seed: int = 42) -> list[tuple[float, float, float]]:
    """n points restricted to the upper hemisphere (z > 0) — low coverage."""
    rng = np.random.default_rng(seed)
    angles = rng.uniform(0, np.pi / 2, size=n)
    phi = rng.uniform(0, 2 * np.pi, size=n)
    r = 40.0
    xs = r * np.sin(angles) * np.cos(phi)
    ys = r * np.sin(angles) * np.sin(phi)
    zs = r * np.cos(angles)
    return [
        (float(x), float(y), float(z))
        for x, y, z in zip(xs, ys, zs, strict=True)
    ]


_FAST_KWARGS = {
    "sample_period_s": 0.001,
    "progress_period_s": 0.005,
}


def _make_service(
    db: aiosqlite.Connection,
    *,
    lis_samples: list[tuple[float, float, float]] | None = None,
    **kwargs,
) -> CalibrationServiceImpl:
    lis_s = lis_samples if lis_samples is not None else _full_sphere_samples(1_000)
    return CalibrationServiceImpl(
        db=db,
        lis3mdl=FakeLis3mdlAdapter(lis_s),
        **{**_FAST_KWARGS, **kwargs},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_start_creates_session(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("lis3mdl")

    assert isinstance(sid, str) and len(sid) == 32
    session = await svc.current_session()
    assert session == (sid, "lis3mdl")
    # State is sampling after start.
    assert svc._state == "sampling"

    await svc.abort(sid)


async def test_concurrent_start_raises_conflict(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("lis3mdl")
    try:
        with pytest.raises(ConflictError):
            await svc.start("lis3mdl")
    finally:
        await svc.abort(sid)


async def test_progress_emits_state_updates(db: aiosqlite.Connection) -> None:
    svc = _make_service(db)
    sid = await svc.start("lis3mdl")

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
    svc = _make_service(db, lis_samples=_full_sphere_samples(1_000))
    sid = await svc.start("lis3mdl")

    # Let sampling accumulate past lis3mdl_min_samples (default 500).
    await asyncio.sleep(0.7)

    status = await svc.finalize(sid)

    # Returned status is persisted.
    assert status.sensor_id == "lis3mdl"
    assert status.calibrated_at is not None
    assert status.payload is not None
    assert isinstance(status.payload, Lis3mdlOffsets)
    assert status.payload.coverage_pct >= 80.0

    # Verify DB was actually written.
    db_status = await calibration_repo.get_offsets(db, "lis3mdl")
    assert db_status.calibrated_at is not None

    # Session must be cleared.
    assert await svc.current_session() is None


async def test_abort_resets_to_idle_without_writing_db(
    db: aiosqlite.Connection,
) -> None:
    svc = _make_service(db)
    sid = await svc.start("lis3mdl")
    await asyncio.sleep(0.02)
    await svc.abort(sid)

    # DB must remain empty.
    db_status = await calibration_repo.get_offsets(db, "lis3mdl")
    assert db_status.calibrated_at is None
    assert db_status.payload is None

    # Session cleared.
    assert await svc.current_session() is None
    assert svc._state == "aborted"


async def test_finalize_before_threshold_raises(db: aiosqlite.Connection) -> None:
    svc = _make_service(db, lis3mdl_min_samples=500)
    sid = await svc.start("lis3mdl")
    # Sleep briefly — far fewer samples than lis3mdl_min_samples accumulate.
    await asyncio.sleep(0.02)
    # Force a deterministic sample count regardless of scheduling jitter.
    svc._samples = svc._samples[:50]

    with pytest.raises(ValueError, match="insufficient samples"):
        await svc.finalize(sid)

    # Session must be cleared after the error.
    assert await svc.current_session() is None


async def test_lis3mdl_coverage_threshold(db: aiosqlite.Connection) -> None:
    """500 hemisphere-only samples (z>0) → coverage too low → finalize raises."""
    hemi_samples = _hemisphere_samples(600)

    svc = CalibrationServiceImpl(
        db=db,
        lis3mdl=FakeLis3mdlAdapter(hemi_samples),
        sample_period_s=0.001,
        progress_period_s=0.005,
        lis3mdl_min_samples=500,
        lis3mdl_coverage_threshold=80.0,
    )
    sid = await svc.start("lis3mdl")
    # Force the deterministic sample set instead of waiting on the sampling
    # loop's wall-clock timing: at 500 samples × 1ms/sample, a fixed
    # asyncio.sleep(0.7) races against real scheduling jitter (event loop
    # load, CI slowness) and can land under lis3mdl_min_samples, raising
    # "insufficient samples" instead of the "coverage" error under test —
    # the same deterministic-override pattern is already used in
    # test_finalize_before_threshold_raises above.
    svc._samples = list(hemi_samples)

    with pytest.raises(ValueError, match="coverage"):
        await svc.finalize(sid)

    assert await svc.current_session() is None
