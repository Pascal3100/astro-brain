"""``GET /state`` — one-shot full state snapshot for clients to (re)sync."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from astro_brain import deps
from astro_brain.bus import StateBus

router = APIRouter(tags=["state"])


@router.get("/state")
async def get_state(bus: StateBus = Depends(deps.get_bus)) -> dict[str, Any]:
    """Return the current :class:`SystemState` serialized as JSON."""
    return bus.get_full_state().to_dict()
