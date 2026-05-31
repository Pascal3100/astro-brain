"""Route REST GoTo : POST /goto (slew vers coordonnées sur monture alignée).

L'abort se fait via le POST /stop existant (TELESCOPE_ABORT_MOTION).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from astro_brain import deps
from astro_brain.api_models import OkResponse
from astro_brain.bus import StateBus
from astro_brain.services.interfaces import AlignmentService, MountService

router = APIRouter(tags=["goto"])


class GotoRequest(BaseModel):
    ra_deg: float = Field(ge=0.0, lt=360.0)
    dec_deg: float = Field(ge=-90.0, le=90.0)
    target_name: str | None = None


@router.post("/goto", response_model=OkResponse)
async def goto(
    req: GotoRequest,
    mount: MountService = Depends(deps.get_mount),
    alignment: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> OkResponse:
    if not alignment.is_aligned:
        raise HTTPException(status_code=409, detail="mount not aligned")
    mount_state = bus.get_full_state().subsystems.get("mount")
    if mount_state is not None and mount_state.details.get("goto_in_progress"):
        raise HTTPException(status_code=409, detail="goto already in progress")
    await mount.goto_radec(req.ra_deg, req.dec_deg, target_name=req.target_name)
    return OkResponse()
