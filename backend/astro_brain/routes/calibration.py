"""Calibration REST + SSE routes.

All endpoints are mounted under ``/calibration/{sensor_id}/…``.

Error mapping
-------------
* Unknown ``sensor_id``          → 400 ``{"detail": "unknown sensor_id"}``
* :class:`~astro_brain.services.interfaces.ConflictError` from ``start``
                                 → 409 ``{"detail": <message>}``
* No active session for ``finalize``
                                 → 404 ``{"detail": "no active session for <id>"}``
* Threshold failure from ``finalize``
                                 → 422 ``{"detail": <message>}``
* :class:`~astro_brain.services.interfaces.SensorUnavailableError` (chip
  absent or unpowered) from ``start``
                                 → 503 ``{"detail": <message>}``
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from astro_brain import deps
from astro_brain.models.calibration import CalibrationStatus
from astro_brain.repository.calibration_repo import SENSOR_IDS, get_offsets
from astro_brain.services.interfaces import (
    CalibrationService,
    ConflictError,
    SensorUnavailableError,
)

router = APIRouter(tags=["calibration"])

_PING_S = 15


def _validate_sensor_id(sensor_id: str) -> None:
    """Raise ``HTTPException(400)`` when *sensor_id* is not recognised."""
    if sensor_id not in SENSOR_IDS:
        raise HTTPException(status_code=400, detail="unknown sensor_id")


# ---------------------------------------------------------------------------
# POST /calibration/{sensor_id}/start
# ---------------------------------------------------------------------------


@router.post("/calibration/{sensor_id}/start")
async def start_calibration(
    sensor_id: str,
    service: CalibrationService = Depends(deps.get_calibration_service),
) -> JSONResponse:
    """Begin a calibration session for *sensor_id*.

    Returns ``202 Accepted`` with ``{"session_id": "<hex>"}`` on success,
    ``503`` when the sensor does not answer on its bus.
    """
    _validate_sensor_id(sensor_id)
    try:
        session_id = await service.start(sensor_id)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SensorUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JSONResponse({"session_id": session_id}, status_code=202)


# ---------------------------------------------------------------------------
# GET /calibration/{sensor_id}/stream?session_id=<hex>
# ---------------------------------------------------------------------------


@router.get("/calibration/{sensor_id}/stream")
async def stream_calibration(
    sensor_id: str,
    request: Request,
    session_id: str = Query(...),
    service: CalibrationService = Depends(deps.get_calibration_service),
) -> EventSourceResponse:
    """SSE stream of :class:`~astro_brain.models.calibration.CalibrationProgress`.

    Yields ``progress`` events while the session is active, then a final
    ``end`` event when the stream terminates.  Disconnecting the client
    does **not** abort the session.
    """
    _validate_sensor_id(sensor_id)

    current = await service.current_session()
    if current is None or current[0] != session_id:
        raise HTTPException(
            status_code=404,
            detail=f"session {session_id!r} is not active",
        )

    async def _gen() -> AsyncIterator[dict[str, Any]]:
        async for progress in service.progress(session_id):
            if await request.is_disconnected():
                break
            yield {"event": "progress", "data": progress.model_dump_json()}
        yield {"event": "end", "data": "{}"}

    return EventSourceResponse(_gen(), ping=_PING_S)


# ---------------------------------------------------------------------------
# POST /calibration/{sensor_id}/finalize
# ---------------------------------------------------------------------------


@router.post("/calibration/{sensor_id}/finalize")
async def finalize_calibration(
    sensor_id: str,
    service: CalibrationService = Depends(deps.get_calibration_service),
) -> CalibrationStatus:
    """Stop sampling, run the math, persist offsets, and return the result.

    Returns ``404`` when no session is active for *sensor_id*, and ``422``
    when the quality thresholds are not met.
    """
    _validate_sensor_id(sensor_id)

    current = await service.current_session()
    if current is None or current[1] != sensor_id:
        raise HTTPException(
            status_code=404,
            detail=f"no active session for {sensor_id}",
        )
    session_id, _ = current
    try:
        return await service.finalize(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /calibration/{sensor_id}/abort
# ---------------------------------------------------------------------------


@router.post("/calibration/{sensor_id}/abort")
async def abort_calibration(
    sensor_id: str,
    service: CalibrationService = Depends(deps.get_calibration_service),
) -> dict[str, bool]:
    """Cancel the active calibration session without persisting any data.

    Idempotent — returns ``{"ok": true}`` even when no session is active.
    """
    _validate_sensor_id(sensor_id)

    current = await service.current_session()
    if current is not None and current[1] == sensor_id:
        await service.abort(current[0])
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /calibration/{sensor_id}
# ---------------------------------------------------------------------------


@router.get("/calibration/{sensor_id}")
async def get_calibration_status(
    sensor_id: str,
    request: Request,
    service: CalibrationService = Depends(deps.get_calibration_service),
) -> CalibrationStatus:
    """Return the persisted calibration for *sensor_id*.

    Always ``200``; ``payload`` is ``null`` when the sensor has never been
    calibrated.
    """
    _validate_sensor_id(sensor_id)
    db = request.app.state.db
    return await get_offsets(db, sensor_id)
