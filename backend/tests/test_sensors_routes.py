"""Integration tests for /sensors/tilt/stream and /sensors/compass/stream SSE routes."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import aiosqlite
import pytest
from fastapi import FastAPI

from astro_brain.models.calibration import Adxl345Offsets, Lis3mdlOffsets
from astro_brain.repository.calibration_repo import upsert_offsets
from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.sensors import (
    _LazySensor,
    compass_stream,
    router,
    tilt_stream,
)

# ---------------------------------------------------------------------------
# Minimal fake adapters
# ---------------------------------------------------------------------------


class _FakeAdxl345:
    """Programmable ADXL345 fake that cycles through a sample list."""

    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = samples
        self._idx = 0
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def read_raw_g(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


class _FakeLis3mdl:
    """Programmable LIS3MDL fake that cycles through a sample list."""

    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = samples
        self._idx = 0
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def read_raw(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# App builder helpers
# ---------------------------------------------------------------------------


def _make_tilt_app(
    db: aiosqlite.Connection,
    adxl_tube: _FakeAdxl345,
) -> FastAPI:
    """Build a minimal app for tilt stream tests."""
    app = FastAPI()
    app.state.db = db
    app.state.lazy_adxl_tube = _LazySensor(adxl_tube)
    app.include_router(router)
    return app


def _make_compass_app(
    db: aiosqlite.Connection,
    adxl_mount: _FakeAdxl345,
    lis3mdl: _FakeLis3mdl,
) -> FastAPI:
    """Build a minimal app for compass stream tests."""
    app = FastAPI()
    app.state.db = db
    app.state.lazy_adxl_mount = _LazySensor(adxl_mount)
    app.state.lazy_lis3mdl = _LazySensor(lis3mdl)
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# SSE helper — collect N events from the body_iterator
# ---------------------------------------------------------------------------


async def _collect_events(
    response: object,
    *,
    count: int,
    timeout: float = 5.0,
) -> list[dict]:
    """Collect *count* SSE event dicts from *response.body_iterator*."""
    it = response.body_iterator  # type: ignore[attr-defined]
    events: list[dict] = []
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while len(events) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            ev = await asyncio.wait_for(it.__anext__(), timeout=remaining)
            events.append(ev)
    except StopAsyncIteration:
        pass
    finally:
        with contextlib.suppress(Exception):
            await it.aclose()
    return events


# ---------------------------------------------------------------------------
# Test 1 — tilt stream emits at ~5 Hz
# ---------------------------------------------------------------------------


async def test_tilt_stream_emits_at_5hz(db: aiosqlite.Connection) -> None:
    """Consuming the stream for ~1 s at hz=5 should yield at least 4 events."""
    adxl = _FakeAdxl345([(0.0, 0.0, 1.0)] * 1_000_000)
    app = _make_tilt_app(db, adxl)

    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await tilt_stream(
        request=fake_request,
        hz=5,
        lazy_adxl_tube=app.state.lazy_adxl_tube,
        db=db,
    )

    t_start = asyncio.get_event_loop().time()
    events = await _collect_events(response, count=5, timeout=2.0)
    t_elapsed = asyncio.get_event_loop().time() - t_start

    assert len(events) >= 4, f"expected ≥4 events in ~1 s, got {len(events)}"

    for ev in events:
        assert ev["event"] == "tilt"
        data = json.loads(ev["data"])
        assert abs(data["pitch_deg"]) < 0.1, f"pitch {data['pitch_deg']!r} not ~0"
        assert abs(data["roll_deg"]) < 0.1, f"roll {data['roll_deg']!r} not ~0"

    # 5 events in ≤1.2 s is consistent with 5 Hz (allow some scheduling slack)
    assert t_elapsed < 1.5, f"too slow: {t_elapsed:.2f} s for {len(events)} events"


# ---------------------------------------------------------------------------
# Test 2 — tilt stream applies persisted offsets
# ---------------------------------------------------------------------------


async def test_tilt_stream_applies_persisted_offsets(
    db: aiosqlite.Connection,
) -> None:
    """Bias subtraction must yield the corrected sample for pitch/roll computation."""
    # Write calibration offsets to DB.
    bias = (0.1, 0.05, 0.05)
    await upsert_offsets(db, "adxl345_tube", Adxl345Offsets(bias=bias, sigma=0.01))

    # Fake emits (0.2, 0.1, 1.05) → corrected = (0.1, 0.05, 1.0)
    raw_sample = (0.2, 0.1, 1.05)
    adxl = _FakeAdxl345([raw_sample] * 1_000_000)
    app = _make_tilt_app(db, adxl)

    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await tilt_stream(
        request=fake_request,
        hz=10,
        lazy_adxl_tube=app.state.lazy_adxl_tube,
        db=db,
    )

    events = await _collect_events(response, count=1, timeout=2.0)
    assert len(events) == 1

    data = json.loads(events[0]["data"])

    # Expected from corrected sample (0.1, 0.05, 1.0)
    x, y, z = 0.1, 0.05, 1.0
    expected_pitch = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
    expected_roll = math.degrees(math.atan2(y, z))
    expected_mag = math.sqrt(x * x + y * y + z * z)

    assert abs(data["pitch_deg"] - expected_pitch) < 0.1
    assert abs(data["roll_deg"] - expected_roll) < 0.1
    assert abs(data["magnitude_g"] - expected_mag) < 1e-6
    assert data["calibrated"] is True


# ---------------------------------------------------------------------------
# Test 3 — tilt stream sets calibrated=false when no DB row
# ---------------------------------------------------------------------------


async def test_tilt_stream_uncalibrated_flag_false(
    db: aiosqlite.Connection,
) -> None:
    """No DB row → calibrated must be false in every emitted event."""
    adxl = _FakeAdxl345([(0.1, 0.2, 0.9)] * 1_000_000)
    app = _make_tilt_app(db, adxl)

    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await tilt_stream(
        request=fake_request,
        hz=10,
        lazy_adxl_tube=app.state.lazy_adxl_tube,
        db=db,
    )

    events = await _collect_events(response, count=3, timeout=2.0)
    assert len(events) >= 1

    for ev in events:
        data = json.loads(ev["data"])
        assert data["calibrated"] is False


# ---------------------------------------------------------------------------
# Test 4 — compass stream flags (3 cases)
# ---------------------------------------------------------------------------


async def test_compass_stream_includes_calibrated_and_tilt_compensated_flags(
    db: aiosqlite.Connection,
) -> None:
    """Three cases: no cal, only LIS3MDL cal, both cal."""
    _RAW_MAG = (50.0, 0.0, 30.0)
    _RAW_ACCEL = (0.0, 0.0, 1.0)
    _IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

    async def _one_event(
        db_: aiosqlite.Connection,
    ) -> dict:
        adxl = _FakeAdxl345([_RAW_ACCEL] * 1_000_000)
        lis = _FakeLis3mdl([_RAW_MAG] * 1_000_000)
        app_ = _make_compass_app(db_, adxl, lis)

        fake_request = AsyncMock()
        fake_request.app = app_
        fake_request.is_disconnected = AsyncMock(return_value=False)

        response = await compass_stream(
            request=fake_request,
            hz=10,
            lazy_adxl_mount=app_.state.lazy_adxl_mount,
            lazy_lis3mdl=app_.state.lazy_lis3mdl,
            db=db_,
        )
        evs = await _collect_events(response, count=1, timeout=2.0)
        assert len(evs) == 1
        return json.loads(evs[0]["data"])

    # Case A — no calibration
    data_a = await _one_event(db)
    assert data_a["calibrated"] is False
    assert data_a["tilt_compensated"] is False

    # Case B — only LIS3MDL calibrated
    await upsert_offsets(
        db,
        "lis3mdl",
        Lis3mdlOffsets(
            offsets=(0.0, 0.0, 0.0),
            scale_matrix=_IDENTITY,
            coverage_pct=100.0,
            residual=0.01,
        ),
    )
    data_b = await _one_event(db)
    assert data_b["calibrated"] is True
    assert data_b["tilt_compensated"] is False

    # Case C — both calibrated
    await upsert_offsets(
        db,
        "adxl345_mount",
        Adxl345Offsets(bias=(0.0, 0.0, 0.0), sigma=0.01),
    )
    data_c = await _one_event(db)
    assert data_c["calibrated"] is True
    assert data_c["tilt_compensated"] is True


# ---------------------------------------------------------------------------
# Test 5 — compass stream corrects mag with persisted offsets
# ---------------------------------------------------------------------------


async def test_compass_stream_corrects_mag_with_persisted_offsets(
    db: aiosqlite.Connection,
) -> None:
    """LIS3MDL hard-iron offset (10,0,0) and identity scale → corrected (50,0,30)."""
    _IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    await upsert_offsets(
        db,
        "lis3mdl",
        Lis3mdlOffsets(
            offsets=(10.0, 0.0, 0.0),
            scale_matrix=_IDENTITY,
            coverage_pct=90.0,
            residual=0.01,
        ),
    )

    raw_mag = (60.0, 0.0, 30.0)
    adxl = _FakeAdxl345([(0.0, 0.0, 1.0)] * 1_000_000)
    lis = _FakeLis3mdl([raw_mag] * 1_000_000)
    app = _make_compass_app(db, adxl, lis)

    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await compass_stream(
        request=fake_request,
        hz=10,
        lazy_adxl_mount=app.state.lazy_adxl_mount,
        lazy_lis3mdl=app.state.lazy_lis3mdl,
        db=db,
    )

    events = await _collect_events(response, count=1, timeout=2.0)
    assert len(events) == 1

    data = json.loads(events[0]["data"])

    # Corrected = (60-10, 0-0, 30-0) = (50, 0, 30)
    cx, cy, cz = 50.0, 0.0, 30.0
    expected_heading = math.degrees(math.atan2(cy, cx)) % 360.0
    expected_mag_ut = math.sqrt(cx * cx + cy * cy + cz * cz)

    assert abs(data["heading_deg"] - expected_heading) < 0.01
    assert abs(data["magnitude_uT"] - expected_mag_ut) < 0.01
    assert data["calibrated"] is True
    assert data["tilt_compensated"] is False  # no mount accel calibration

    # raw should reflect the uncorrected sample
    assert data["raw"]["x"] == pytest.approx(60.0)
    assert data["raw"]["y"] == pytest.approx(0.0)
    assert data["raw"]["z"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Test 6 — hz hors plage [1, 10] → 422
# ---------------------------------------------------------------------------


async def test_hz_out_of_range_rejected(db: aiosqlite.Connection) -> None:
    """hz=0 et hz=20 doivent renvoyer 422 (rejet explicite, pas un clamp)."""
    from fastapi import HTTPException

    _RAW = (0.0, 0.0, 1.0)

    async def _call(hz_param: int) -> None:
        adxl = _FakeAdxl345([_RAW] * 1_000)
        app = _make_tilt_app(db, adxl)
        fake_request = AsyncMock()
        fake_request.app = app
        fake_request.is_disconnected = AsyncMock(return_value=False)

        await tilt_stream(
            request=fake_request,
            hz=hz_param,
            lazy_adxl_tube=app.state.lazy_adxl_tube,
            db=db,
        )

    for bad_hz in (0, -1, 11, 20):
        with pytest.raises(HTTPException) as excinfo:
            await _call(bad_hz)
        assert excinfo.value.status_code == 422
        assert "hz" in excinfo.value.detail.lower()


# ---------------------------------------------------------------------------
# Test bonus — _LazySensor start/stop lifecycle
# ---------------------------------------------------------------------------


async def test_lazy_sensor_start_stop_lifecycle() -> None:
    """_LazySensor must call start once on first enter and stop once after last exit."""
    adxl = _FakeAdxl345([(0.0, 0.0, 1.0)] * 10)
    lazy = _LazySensor(adxl)

    assert adxl.start_calls == 0
    assert adxl.stop_calls == 0

    async with lazy:
        assert adxl.start_calls == 1
        assert adxl.stop_calls == 0
        async with lazy:
            assert adxl.start_calls == 1  # not called again
            assert adxl.stop_calls == 0
        assert adxl.stop_calls == 0  # still one ref

    assert adxl.stop_calls == 1  # now fully released
    assert adxl.start_calls == 1
