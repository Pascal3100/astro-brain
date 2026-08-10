"""Route REST GoTo : POST /goto (résolution par id + slew sur monture alignée).

L'abort se fait via le POST /stop existant (TELESCOPE_ABORT_MOTION).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.api_models import OkResponse
from astro_brain.bus import StateBus
from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.resolver import TargetResolver
from astro_brain.services.interfaces import AlignmentService, MountService

router = APIRouter(tags=["goto"])


class GotoRequest(BaseModel):
    id: str
    confirm_solar: bool = False


@router.post("/goto", response_model=OkResponse)
async def goto(
    req: GotoRequest,
    mount: MountService = Depends(deps.get_mount),
    alignment: AlignmentService = Depends(deps.get_alignment_service),
    resolver: TargetResolver = Depends(deps.get_resolver),
    reference: ReferenceDb = Depends(deps.get_reference_db),
    bus: StateBus = Depends(deps.get_bus),
) -> OkResponse:
    if not reference.ready:
        raise HTTPException(status_code=409, detail="reference_unavailable")
    target = await resolver.resolve(req.id)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown_id")
    if target.stale:
        raise HTTPException(status_code=409, detail="ephemeris_stale")
    if not alignment.is_aligned:
        raise HTTPException(status_code=409, detail="not_aligned")
    mount_state = bus.get_full_state().subsystems.get("mount")
    if mount_state is not None and mount_state.details.get("goto_in_progress"):
        raise HTTPException(status_code=409, detail="goto_in_progress")
    if target.kind == "sun" and not req.confirm_solar:
        raise HTTPException(status_code=409, detail="solar_ack_required")
    await mount.goto_radec(target.ra_deg, target.dec_deg, target_name=target.name)
    return OkResponse()
