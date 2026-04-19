"""``GET /state`` — one-shot full state snapshot for clients to (re)sync."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from astro_brain import deps

router = APIRouter(tags=["state"])


@router.get("/state")
async def get_state() -> dict[str, Any]:
    """Return the current :class:`SystemState` serialized as JSON."""
    return deps.get_bus().get_full_state().to_dict()
