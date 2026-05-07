"""Live sensor streams: /sensors/tilt + /sensors/compass (SSE)."""

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
from astro_brain.models.calibration import Adxl345Offsets, Lis3mdlOffsets
from astro_brain.repository import calibration_repo
from astro_brain.services._tilt_compensated_heading import (
    naive_heading,
    tilt_compensated_heading,
)

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
    this in practice (the tilt/compass screens are not accessible during
    calibration), so this is acceptable in v0.2.
    """

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._lock = asyncio.Lock()
        self._refcount = 0

    async def __aenter__(self) -> Any:
        async with self._lock:
            if self._refcount == 0:
                await self._adapter.start()
            self._refcount += 1
        return self._adapter

    async def __aexit__(self, *args: Any) -> None:
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


# ---------------------------------------------------------------------------
# GET /sensors/tilt/stream
# ---------------------------------------------------------------------------


@router.get("/sensors/tilt/stream")
async def tilt_stream(
    request: Request,
    hz: int = Query(default=5),
    lazy_adxl_tube: Any = Depends(deps.get_lazy_adxl_tube),
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> EventSourceResponse:
    """SSE stream of tilt readings from the ADXL345 tube sensor.

    Emits one ``tilt`` event per tick at the requested rate. ``hz`` doit être
    dans [1, 10], sinon 422. Calibration offsets are read once at stream-open
    time.
    """
    rate = _validate_hz(hz)

    # Read calibration once per stream connection — not per tick.
    tube_status = await calibration_repo.get_offsets(db, "adxl345_tube")
    tube_offsets: Adxl345Offsets | None = (
        tube_status.payload if isinstance(tube_status.payload, Adxl345Offsets) else None
    )

    async def _gen() -> AsyncIterator[dict[str, Any]]:
        async with lazy_adxl_tube as adxl:
            period = 1.0 / rate
            while True:
                if await request.is_disconnected():
                    break

                raw = await adxl.read_raw_g()
                rx, ry, rz = raw

                if tube_offsets is not None:
                    bx, by, bz = tube_offsets.bias
                    x, y, z = rx - bx, ry - by, rz - bz
                    calibrated = True
                else:
                    x, y, z = rx, ry, rz
                    calibrated = False

                pitch_deg = math.degrees(math.atan2(-x, math.sqrt(y * y + z * z)))
                roll_deg = math.degrees(math.atan2(y, z))
                magnitude_g = math.sqrt(x * x + y * y + z * z)

                payload = {
                    "ts": datetime.now(UTC).isoformat(),
                    "pitch_deg": pitch_deg,
                    "roll_deg": roll_deg,
                    "magnitude_g": magnitude_g,
                    "calibrated": calibrated,
                }
                yield {"event": "tilt", "data": json.dumps(payload)}
                await asyncio.sleep(period)

    return EventSourceResponse(_gen(), ping=_PING_S)


# ---------------------------------------------------------------------------
# GET /sensors/compass/stream
# ---------------------------------------------------------------------------


@router.get("/sensors/compass/stream")
async def compass_stream(
    request: Request,
    hz: int = Query(default=5),
    lazy_adxl_mount: Any = Depends(deps.get_lazy_adxl_mount),
    lazy_lis3mdl: Any = Depends(deps.get_lazy_lis3mdl),
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> EventSourceResponse:
    """SSE stream of compass readings from the LIS3MDL + ADXL345 mount sensors.

    Emits one ``compass`` event per tick at the requested rate. ``hz`` doit
    être dans [1, 10], sinon 422. Calibration offsets are read once at
    stream-open time. When both sensors are calibrated, heading is
    tilt-compensated.
    """
    rate = _validate_hz(hz)

    # Read calibration once per stream connection — not per tick.
    mag_status = await calibration_repo.get_offsets(db, "lis3mdl")
    mag_offsets: Lis3mdlOffsets | None = (
        mag_status.payload if isinstance(mag_status.payload, Lis3mdlOffsets) else None
    )

    mount_status = await calibration_repo.get_offsets(db, "adxl345_mount")
    mount_offsets: Adxl345Offsets | None = (
        mount_status.payload
        if isinstance(mount_status.payload, Adxl345Offsets)
        else None
    )

    async def _gen() -> AsyncIterator[dict[str, Any]]:
        async with lazy_lis3mdl as lis3mdl, lazy_adxl_mount as adxl_mount:
            period = 1.0 / rate
            while True:
                if await request.is_disconnected():
                    break

                raw_mag = await lis3mdl.read_raw()
                raw_accel = await adxl_mount.read_raw_g()

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

                # Apply accel bias when calibrated.
                if mount_offsets is not None:
                    bx, by, bz = mount_offsets.bias
                    ax, ay, az = raw_accel
                    corrected_accel: tuple[float, float, float] = (
                        ax - bx,
                        ay - by,
                        az - bz,
                    )
                    heading_deg = tilt_compensated_heading(corrected_mag, corrected_accel)
                    tilt_compensated = True
                else:
                    heading_deg = naive_heading(corrected_mag)
                    tilt_compensated = False

                magnitude_ut = math.sqrt(cmx * cmx + cmy * cmy + cmz * cmz)

                payload = {
                    "ts": datetime.now(UTC).isoformat(),
                    "heading_deg": heading_deg,
                    "magnitude_uT": magnitude_ut,
                    "raw": {"x": rmx, "y": rmy, "z": rmz},
                    "tilt_compensated": tilt_compensated,
                    "calibrated": calibrated,
                }
                yield {"event": "compass", "data": json.dumps(payload)}
                await asyncio.sleep(period)

    return EventSourceResponse(_gen(), ping=_PING_S)
