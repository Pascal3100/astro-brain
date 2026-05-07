"""Mount limits REST routes (altitude only in v0.2).

All endpoints are mounted under ``/limits/…``.

Error mapping
-------------
* ``GET /limits/alt`` when never set    → 404 ``{"detail": "alt limits not set"}``
* ``PUT /limits/alt`` with invalid body → 422 (auto, via :class:`AltLimits`
  ``model_validator``: ``min_deg < max_deg`` and a 30° minimum range).
"""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from astro_brain import deps
from astro_brain.models.calibration import AltLimits
from astro_brain.repository.limits_repo import get_alt_limits, set_alt_limits

router = APIRouter(tags=["limits"])


# ---------------------------------------------------------------------------
# GET /limits/alt
# ---------------------------------------------------------------------------


@router.get("/limits/alt")
async def get_alt_limits_route(
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> AltLimits:
    """Return the persisted altitude limits.

    Responds ``404`` when the limits have never been set.
    """
    limits = await get_alt_limits(db)
    if limits is None:
        raise HTTPException(status_code=404, detail="alt limits not set")
    return limits


# ---------------------------------------------------------------------------
# PUT /limits/alt
# ---------------------------------------------------------------------------


@router.put("/limits/alt")
async def put_alt_limits_route(
    limits: AltLimits,
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> AltLimits:
    """Persist the altitude limits and echo them back.

    Body validation (ordered bounds, 30° minimum range) is enforced by the
    :class:`AltLimits` ``model_validator`` and yields ``422`` on failure.
    """
    await set_alt_limits(db, limits)
    return limits
