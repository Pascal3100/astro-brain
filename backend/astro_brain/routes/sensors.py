"""Live sensor stream: /sensors/compass (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from astro_brain import deps
from astro_brain.models.calibration import Lis3mdlOffsets
from astro_brain.repository import calibration_repo
from astro_brain.services._heading import naive_heading
from astro_brain.services.interfaces import SensorUnavailableError

router = APIRouter(tags=["sensors"])

_log = logging.getLogger(__name__)

_PING_S = 15
_HZ_MIN = 1
_HZ_MAX = 10


def _validate_hz(hz: int) -> int:
    """Reject hz hors plage [1, 10] avec un 422 explicite."""
    if hz < _HZ_MIN or hz > _HZ_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"hz must be in [{_HZ_MIN}, {_HZ_MAX}], got {hz}",
        )
    return hz


class _LazySensor:
    """Reference-counted async context manager that lazily starts/stops an adapter.

    The adapter is started on the first subscriber and stopped when the last
    subscriber disconnects.

    Note: calibration sessions also call ``adapter.start()`` / ``adapter.stop()``
    directly.  Opening a live sensor stream while a calibration session is active
    will call ``start()`` a second time, which is idempotent on the fake adapters
    and merely re-writes init registers on the real chips.  The UI flow prevents
    this in practice (the compass screen is not accessible during calibration),
    so this is acceptable in v0.2.
    """

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._lock = asyncio.Lock()
        self._refcount = 0

    async def acquire(self) -> Any:
        """Start the adapter if this is the first subscriber, and return it.

        Exposed separately from :meth:`__aenter__` so a route can acquire the
        sensor *before* committing to a response: a failure raised from inside
        a streaming generator can no longer become an HTTP status.

        Raises:
            SensorUnavailableError: The chip did not answer on its bus.
        """
        async with self._lock:
            if self._refcount == 0:
                await self._adapter.start()
            self._refcount += 1
        return self._adapter

    async def release(self) -> None:
        """Drop one subscriber, stopping the adapter when the last one goes."""
        async with self._lock:
            self._refcount -= 1
            if self._refcount == 0:
                # Une exception dans stop() ne doit pas faire dériver le refcount.
                try:
                    await self._adapter.stop()
                except Exception as exc:
                    _log.warning(
                        "LazySensor adapter.stop() error: %s", exc
                    )

    async def __aenter__(self) -> Any:
        return await self.acquire()

    async def __aexit__(self, *args: Any) -> None:
        await self.release()


# ---------------------------------------------------------------------------
# GET /sensors/compass/stream
# ---------------------------------------------------------------------------


@router.get("/sensors/compass/stream")
async def compass_stream(
    request: Request,
    hz: int = Query(default=5),
    lazy_lis3mdl: Any = Depends(deps.get_lazy_lis3mdl),
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> EventSourceResponse:
    """SSE stream of compass readings from the LIS3MDL magnetometer.

    Emits one ``compass`` event per tick at the requested rate. ``hz`` doit
    être dans [1, 10], sinon 422. Calibration offsets are read once at
    stream-open time. Heading is always naive (no tilt compensation — the
    mount accelerometer that used to provide it has been removed).
    """
    rate = _validate_hz(hz)

    # Read calibration once per stream connection — not per tick.
    mag_status = await calibration_repo.get_offsets(db, "lis3mdl")
    mag_offsets: Lis3mdlOffsets | None = (
        mag_status.payload if isinstance(mag_status.payload, Lis3mdlOffsets) else None
    )

    # Le capteur est acquis AVANT de rendre la réponse : une fois les en-têtes
    # SSE partis, une panne matérielle ne peut plus devenir un statut HTTP —
    # elle s'échappe dans la couche ASGI et le client reçoit un corps chunké
    # tronqué. C'est ce qui arrivait avec le LIS3MDL débranché.
    try:
        lis3mdl = await lazy_lis3mdl.acquire()
    except SensorUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def _gen() -> AsyncIterator[dict[str, Any]]:
        try:
            period = 1.0 / rate
            while True:
                if await request.is_disconnected():
                    break

                try:
                    raw_mag = await lis3mdl.read_raw()
                except SensorUnavailableError as exc:
                    # Puce arrachée en cours de flux : le dire dans le flux et
                    # fermer, plutôt que tronquer le corps.
                    _log.warning("compass stream interrompu: %s", exc)
                    yield {
                        "event": "error",
                        "data": json.dumps({"detail": str(exc)}),
                    }
                    break

                rmx, rmy, rmz = raw_mag

                # Apply soft-iron + hard-iron correction when calibrated.
                if mag_offsets is not None:
                    ox, oy, oz = mag_offsets.offsets
                    s = mag_offsets.scale_matrix
                    # corrected = scale_matrix @ (raw - offsets)
                    dx, dy, dz = rmx - ox, rmy - oy, rmz - oz
                    cmx = s[0][0] * dx + s[0][1] * dy + s[0][2] * dz
                    cmy = s[1][0] * dx + s[1][1] * dy + s[1][2] * dz
                    cmz = s[2][0] * dx + s[2][1] * dy + s[2][2] * dz
                    calibrated = True
                else:
                    cmx, cmy, cmz = rmx, rmy, rmz
                    calibrated = False

                corrected_mag: tuple[float, float, float] = (cmx, cmy, cmz)

                heading_deg = naive_heading(corrected_mag)

                magnitude_ut = math.sqrt(cmx * cmx + cmy * cmy + cmz * cmz)

                payload = {
                    "ts": datetime.now(UTC).isoformat(),
                    "heading_deg": heading_deg,
                    "magnitude_uT": magnitude_ut,
                    "raw": {"x": rmx, "y": rmy, "z": rmz},
                    "tilt_compensated": False,
                    "calibrated": calibrated,
                }
                yield {"event": "compass", "data": json.dumps(payload)}
                await asyncio.sleep(period)
        finally:
            await lazy_lis3mdl.release()

    return EventSourceResponse(_gen(), ping=_PING_S)
