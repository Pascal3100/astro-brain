"""Imperative REST commands: ``POST /slew``, ``POST /stop``, ``POST /tracking``."""

from __future__ import annotations

from fastapi import APIRouter

from astro_brain import deps
from astro_brain.api_models import (
    OkResponse,
    SlewRequest,
    StopRequest,
    TrackingRequest,
)

router = APIRouter(tags=["commands"])


@router.post("/slew", response_model=OkResponse)
async def slew(req: SlewRequest) -> OkResponse:
    """Start slewing the mount on one axis."""
    mount = deps.get_mount()
    await mount.slew(req.axis, req.direction, req.rate)
    return OkResponse()


@router.post("/stop", response_model=OkResponse)
async def stop(req: StopRequest) -> OkResponse:
    """Stop slewing. Omitting ``axis`` stops every active slew."""
    mount = deps.get_mount()
    await mount.stop_slew(req.axis)
    return OkResponse()


@router.post("/tracking", response_model=OkResponse)
async def tracking(req: TrackingRequest) -> OkResponse:
    """Enable or disable sidereal tracking."""
    svc = deps.get_tracking()
    await svc.set_tracking(req.enabled)
    return OkResponse()
