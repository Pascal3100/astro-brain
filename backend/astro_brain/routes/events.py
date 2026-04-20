"""``GET /events`` — Server-Sent Events stream of system state updates.

The stream wraps :meth:`StateBus.subscribe` in an
:class:`EventSourceResponse`. It yields one ``snapshot`` event on connect
then one ``update`` event per :meth:`StateBus.publish`. ``sse-starlette``
injects a ``: ping`` comment every :data:`PING_INTERVAL_SECONDS` to keep
the connection alive through reverse-proxies.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from astro_brain import deps
from astro_brain.bus import StateBus

router = APIRouter(tags=["events"])

PING_INTERVAL_SECONDS = 15


@router.get("/events")
async def events(
    request: Request,
    bus: StateBus = Depends(deps.get_bus),
) -> EventSourceResponse:
    """Subscribe to the bus and stream events until the client disconnects."""

    async def event_gen() -> AsyncIterator[dict[str, Any]]:
        async for event in bus.subscribe():
            if await request.is_disconnected():
                break
            yield {"event": event.type, "data": json.dumps(event.payload)}

    return EventSourceResponse(event_gen(), ping=PING_INTERVAL_SECONDS)
