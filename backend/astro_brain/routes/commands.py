"""Imperative REST commands: ``POST /slew``, ``POST /stop``, ``POST /tracking``."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from astro_brain import deps
from astro_brain.api_models import (
    OkResponse,
    SlewRequest,
    StopRequest,
    TrackingRequest,
)
from astro_brain.services.interfaces import MountService, TrackingService

router = APIRouter(tags=["commands"])


@router.post("/slew", response_model=OkResponse)
async def slew(
    req: SlewRequest,
    mount: MountService = Depends(deps.get_mount),
) -> OkResponse:
    """Start slewing the mount on one axis."""
    await mount.slew(req.axis, req.direction, req.rate)
    return OkResponse()


@router.post("/stop", response_model=OkResponse)
async def stop(
    req: StopRequest,
    mount: MountService = Depends(deps.get_mount),
) -> OkResponse:
    """Stop slewing. Omitting ``axis`` stops every active slew."""
    await mount.stop_slew(req.axis)
    return OkResponse()


@router.post("/mount/reconnect", response_model=OkResponse)
async def mount_reconnect(
    mount: MountService = Depends(deps.get_mount),
) -> OkResponse:
    """Trigger a mount reconnect.

    Non-blocking: schedules the reconnect and returns immediately (the app
    uses a short request timeout). Connection progress — ``connecting`` →
    ``ready`` / ``disconnected`` — flows back over SSE ``/state``.
    """
    mount.request_reconnect()
    return OkResponse()


@router.post("/tracking", response_model=OkResponse)
async def tracking(
    req: TrackingRequest,
    svc: TrackingService = Depends(deps.get_tracking),
) -> OkResponse:
    """Enable or disable sidereal tracking."""
    await svc.set_tracking(req.enabled)
    return OkResponse()
