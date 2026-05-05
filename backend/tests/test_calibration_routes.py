"""Integration tests for /calibration/* REST + SSE routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.calibration import router, stream_calibration
from astro_brain.services.calibration import CalibrationServiceImpl

# ---------------------------------------------------------------------------
# Fake adapters (local — richer than the fakes in fakes.py because we need
# to control sample content for threshold tests)
# ---------------------------------------------------------------------------

_IMMOBILE: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0)] * 1_000_000
_EMPTY: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0)] * 1_000_000


class _Adxl345:
    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = samples
        self._idx = 0

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def read_raw_g(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


class _Lis3mdl:
    def __init__(self, samples: list[tuple[float, float, float]]) -> None:
        self._samples = samples
        self._idx = 0

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def read_raw(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


# ---------------------------------------------------------------------------
# Fast timing constants shared across tests
# ---------------------------------------------------------------------------

_FAST = {
    "sample_period_s": 0.001,
    "progress_period_s": 0.005,
    "adxl_min_samples": 100,
}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


def _make_app(
    db: aiosqlite.Connection,
    *,
    adxl_samples: list[tuple[float, float, float]] | None = None,
    **svc_kwargs,
) -> FastAPI:
    """Build a minimal FastAPI app with the calibration router wired."""
    samples = adxl_samples if adxl_samples is not None else _IMMOBILE
    svc = CalibrationServiceImpl(
        db=db,
        adxl_mount=_Adxl345(samples),
        adxl_tube=_Adxl345(samples),
        lis3mdl=_Lis3mdl([(50.0, 0.0, 30.0)] * 1_000_000),
        **{**_FAST, **svc_kwargs},
    )
    app = FastAPI()
    app.state.db = db
    app.state.calibration_service = svc
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_round_trip_start_finalize_status(db: aiosqlite.Connection) -> None:
    """POST start → 202; POST finalize (after samples) → 200; GET status → calibrated."""
    app = _make_app(db)
    with TestClient(app) as client:
        # Start
        r = client.post("/calibration/adxl345_mount/start")
        assert r.status_code == 202, r.text
        session_id = r.json()["session_id"]
        assert len(session_id) == 32

        # Let the sampling task accumulate > 100 samples.
        await asyncio.sleep(0.15)

        # Finalize
        r2 = client.post("/calibration/adxl345_mount/finalize")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["sensor_id"] == "adxl345_mount"
        assert body["calibrated_at"] is not None
        assert body["payload"] is not None

        # GET status
        r3 = client.get("/calibration/adxl345_mount")
        assert r3.status_code == 200, r3.text
        assert r3.json()["calibrated_at"] is not None


async def test_concurrent_start_returns_409(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r1 = client.post("/calibration/adxl345_mount/start")
        assert r1.status_code == 202
        r2 = client.post("/calibration/adxl345_tube/start")
        assert r2.status_code == 409

        # Clean up
        client.post("/calibration/adxl345_mount/abort")


def test_invalid_sensor_id_returns_400(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.post("/calibration/garbage/start")
        assert r.status_code == 400
        assert r.json()["detail"] == "unknown sensor_id"


def test_finalize_no_session_returns_404(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.post("/calibration/adxl345_mount/finalize")
        assert r.status_code == 404


async def test_finalize_below_threshold_returns_422(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.post("/calibration/adxl345_mount/start")
        assert r.status_code == 202
        # Finalize immediately — zero samples collected → insufficient samples.
        r2 = client.post("/calibration/adxl345_mount/finalize")
        assert r2.status_code == 422


def test_get_status_returns_empty_status_when_uncalibrated(
    db: aiosqlite.Connection,
) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.get("/calibration/lis3mdl")
        assert r.status_code == 200
        body = r.json()
        assert body["sensor_id"] == "lis3mdl"
        assert body["calibrated_at"] is None
        assert body["payload"] is None


async def test_abort_clears_session(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r1 = client.post("/calibration/adxl345_mount/start")
        assert r1.status_code == 202

        r2 = client.post("/calibration/adxl345_mount/abort")
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}

        # Starting again must succeed (no 409).
        r3 = client.post("/calibration/adxl345_mount/start")
        assert r3.status_code == 202

        # Clean up.
        client.post("/calibration/adxl345_mount/abort")


async def test_sse_stream_yields_progress_then_end_on_session_clear(
    db: aiosqlite.Connection,
) -> None:
    """Start, open SSE body_iterator, collect progress events, abort, get end event."""
    app = _make_app(db)
    # Extract the calibration service to abort it mid-stream.
    svc = app.state.calibration_service

    session_id = await svc.start("adxl345_mount")

    # Let a few samples accumulate.
    await asyncio.sleep(0.02)

    # Build a fake Request: disconnected=False so the generator keeps running.
    fake_request = AsyncMock()
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await stream_calibration(
        sensor_id="adxl345_mount",
        request=fake_request,
        session_id=session_id,
        service=svc,
    )
    it = response.body_iterator

    # Collect the first progress event.
    first = await asyncio.wait_for(it.__anext__(), timeout=2.0)
    assert first["event"] == "progress"

    # Abort the session in the background — the generator loop exits
    # once current_session no longer matches.
    await svc.abort(session_id)

    # Consume remaining events until we see "end".
    events: list[str] = [first["event"]]
    for _ in range(50):
        try:
            ev = await asyncio.wait_for(it.__anext__(), timeout=1.0)
        except StopAsyncIteration:
            break
        events.append(ev["event"])
        if ev["event"] == "end":
            break

    assert "end" in events, f"expected 'end' event, got: {events}"

    await it.aclose()
