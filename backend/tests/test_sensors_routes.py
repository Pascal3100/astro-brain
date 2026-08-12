"""Integration tests for the /sensors/compass/stream SSE route."""

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

from astro_brain.models.calibration import Lis3mdlOffsets
from astro_brain.repository.calibration_repo import upsert_offsets
from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.sensors import _LazySensor, compass_stream, router
from astro_brain.services.interfaces import SensorUnavailableError

from .fakes.sensor_fakes import FakeLis3mdl as _FakeLis3mdl

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


def _make_compass_app(
    db: aiosqlite.Connection,
    lis3mdl: _FakeLis3mdl,
) -> FastAPI:
    """Build a minimal app for compass stream tests."""
    app = FastAPI()
    app.state.db = db
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
# Test 1 — compass stream flags (2 cases: no cal, LIS3MDL cal)
# ---------------------------------------------------------------------------


async def test_compass_stream_includes_calibrated_and_tilt_compensated_flags(
    db: aiosqlite.Connection,
) -> None:
    """Two cases: no cal, LIS3MDL cal. tilt_compensated is always False."""
    _RAW_MAG = (50.0, 0.0, 30.0)
    _IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

    async def _one_event(
        db_: aiosqlite.Connection,
    ) -> dict:
        lis = _FakeLis3mdl([_RAW_MAG] * 1_000_000)
        app_ = _make_compass_app(db_, lis)

        fake_request = AsyncMock()
        fake_request.app = app_
        fake_request.is_disconnected = AsyncMock(return_value=False)

        response = await compass_stream(
            request=fake_request,
            hz=10,
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

    # Case B — LIS3MDL calibrated
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


# ---------------------------------------------------------------------------
# Test 2 — compass stream corrects mag with persisted offsets
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
    lis = _FakeLis3mdl([raw_mag] * 1_000_000)
    app = _make_compass_app(db, lis)

    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await compass_stream(
        request=fake_request,
        hz=10,
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
    assert data["tilt_compensated"] is False  # no tilt compensation — ADXL removed

    # raw should reflect the uncorrected sample
    assert data["raw"]["x"] == pytest.approx(60.0)
    assert data["raw"]["y"] == pytest.approx(0.0)
    assert data["raw"]["z"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Test 3 — hz hors plage [1, 10] → 422
# ---------------------------------------------------------------------------


async def test_hz_out_of_range_rejected(db: aiosqlite.Connection) -> None:
    """hz=0 et hz=20 doivent renvoyer 422 (rejet explicite, pas un clamp)."""
    from fastapi import HTTPException

    _RAW = (0.0, 0.0, 1.0)

    async def _call(hz_param: int) -> None:
        lis = _FakeLis3mdl([_RAW] * 1_000)
        app = _make_compass_app(db, lis)
        fake_request = AsyncMock()
        fake_request.app = app
        fake_request.is_disconnected = AsyncMock(return_value=False)

        await compass_stream(
            request=fake_request,
            hz=hz_param,
            lazy_lis3mdl=app.state.lazy_lis3mdl,
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
    lis = _FakeLis3mdl([(50.0, 0.0, 30.0)] * 10)
    lazy = _LazySensor(lis)

    assert lis.start_calls == 0
    assert lis.stop_calls == 0

    async with lazy:
        assert lis.start_calls == 1
        assert lis.stop_calls == 0
        async with lazy:
            assert lis.start_calls == 1  # not called again
            assert lis.stop_calls == 0
        assert lis.stop_calls == 0  # still one ref

    assert lis.stop_calls == 1  # now fully released
    assert lis.start_calls == 1


# ---------------------------------------------------------------------------
# Capteur absent — le bench débranché est un état nominal, pas un 500
# ---------------------------------------------------------------------------


class _AbsentLis3mdl(_FakeLis3mdl):
    """Fake dont la puce ne répond pas sur le bus.

    ``fail_after`` samples sont servis avant la panne : 0 simule une puce absente
    au démarrage, n > 0 une puce arrachée en cours de flux.
    """

    def __init__(self, *, fail_after: int = 0) -> None:
        super().__init__([(50.0, 0.0, 30.0)] * 1_000)
        self._fail_after = fail_after
        self._reads = 0

    async def start(self) -> None:
        await super().start()
        if self._fail_after == 0:
            raise SensorUnavailableError("LIS3MDL muet à 0x1E sur i2c-1")

    async def read_raw(self) -> tuple[float, float, float]:
        if self._reads >= self._fail_after:
            raise SensorUnavailableError("LIS3MDL muet à 0x1E sur i2c-1")
        self._reads += 1
        return await super().read_raw()


async def test_absent_sensor_yields_503_not_a_truncated_stream(
    db: aiosqlite.Connection,
) -> None:
    """Puce absente à l'ouverture → 503, avant que les en-têtes SSE ne partent.

    Le capteur doit être acquis *avant* de rendre la réponse : une fois le 200 et
    les en-têtes envoyés, l'échec ne peut plus devenir un statut HTTP et le client
    reçoit un corps chunké tronqué (constaté sur le Pi en S50).
    """
    from fastapi import HTTPException

    lis = _AbsentLis3mdl()
    app = _make_compass_app(db, lis)
    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as excinfo:
        await compass_stream(
            request=fake_request,
            hz=5,
            lazy_lis3mdl=app.state.lazy_lis3mdl,
            db=db,
        )
    assert excinfo.value.status_code == 503
    assert "LIS3MDL" in excinfo.value.detail


async def test_sensor_lost_mid_stream_emits_an_error_event(
    db: aiosqlite.Connection,
) -> None:
    """Puce perdue en vol → un événement ``error`` puis fermeture propre."""
    lis = _AbsentLis3mdl(fail_after=1)
    app = _make_compass_app(db, lis)
    fake_request = AsyncMock()
    fake_request.app = app
    fake_request.is_disconnected = AsyncMock(return_value=False)

    response = await compass_stream(
        request=fake_request,
        hz=10,
        lazy_lis3mdl=app.state.lazy_lis3mdl,
        db=db,
    )
    events = await _collect_events(response, count=3, timeout=2.0)

    assert [ev["event"] for ev in events] == ["compass", "error"]
    assert "LIS3MDL" in json.loads(events[1]["data"])["detail"]
    # Le flux s'est fermé en relâchant le capteur : pas de refcount qui dérive.
    assert lis.stop_calls == 1


async def test_failed_acquire_leaves_no_dangling_refcount() -> None:
    """Un ``acquire()`` en échec ne doit pas consommer une référence.

    Sinon le premier client à trouver la puce absente laisse le refcount à 1 et
    plus jamais aucun ``start()`` n'est retenté — le capteur reste mort même
    rebranché.
    """
    lis = _AbsentLis3mdl()
    lazy = _LazySensor(lis)

    with pytest.raises(SensorUnavailableError):
        await lazy.acquire()
    assert lazy._refcount == 0

    # Puce rebranchée : le prochain client relance bien start().
    lis._fail_after = 1
    adapter = await lazy.acquire()
    assert adapter is lis
    assert lis.start_calls == 2
    await lazy.release()
    assert lis.stop_calls == 1
