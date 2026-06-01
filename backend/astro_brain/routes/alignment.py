"""Routes REST du wizard d'alignement.

Erreurs :
- ConflictError → 409
- ValueError du solver → 422
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
from astro_brain.services.interfaces import AlignmentService, ConflictError
from astro_brain.subsystems import SubsystemState


def _publish_session(bus: StateBus, service: AlignmentService) -> None:
    """Publish the current alignment session state to the bus.

    Called after every mutating route so the SSE stream reflects the wizard
    state in real time. Idempotent (safe to call when nothing changed).
    """
    sess = service.session()
    if sess is None:
        bus.publish(
            "alignment",
            SubsystemState(
                state="idle",
                details={"is_aligned": service.is_aligned},
                since=datetime.now(UTC),
            ),
        )
        return
    bus.publish(
        "alignment",
        SubsystemState(
            state="active",
            details={
                "is_aligned": service.is_aligned,
                "session_id": sess.session_id,
                "current_idx": sess.current_idx,
                "recorded_count": len(sess.recorded_stars),
                "candidate_ids": [c.id for c in sess.candidates],
            },
            since=datetime.now(UTC),
        ),
    )


router = APIRouter(tags=["alignment"], prefix="/align")


class _RecordBody(BaseModel):
    idx: int


class _SwapBody(BaseModel):
    star: Star


class _RestartBody(BaseModel):
    idx: int


@router.get("/session")
async def get_session(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> dict[str, AlignmentSession | None]:
    return {"session": service.session()}


@router.post("/start")
async def start(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.start()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/swap/{idx}")
async def swap(
    idx: int,
    body: _SwapBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.swap(idx, body.star)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/record")
async def record(
    body: _RecordBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.record(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/restart_star")
async def restart_star(
    body: _RestartBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.restart_star(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/finalize")
async def finalize(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentModel:
    try:
        model = await service.finalize()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _publish_session(bus, service)
    return model


@router.delete("/session", status_code=204)
async def cancel(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> Response:
    await service.cancel()
    _publish_session(bus, service)
    return Response(status_code=204)
