"""Routes REST du wizard d'alignement.

Erreurs :
- ConflictError → 409
- ValueError du solver → 422
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
from astro_brain.services.interfaces import AlignmentService, ConflictError

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
) -> AlignmentSession:
    try:
        return await service.start()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/swap/{idx}")
async def swap(
    idx: int,
    body: _SwapBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.swap(idx, body.star)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/record")
async def record(
    body: _RecordBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.record(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/restart_star")
async def restart_star(
    body: _RestartBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.restart_star(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/finalize")
async def finalize(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentModel:
    try:
        return await service.finalize()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/session", status_code=204)
async def cancel(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> Response:
    await service.cancel()
    return Response(status_code=204)
