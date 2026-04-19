"""Tests for the SSE ``GET /events`` handler.

httpx's ``ASGITransport`` and FastAPI's ``TestClient`` both buffer the
entire response body before returning — which makes them unable to
exercise a long-lived SSE stream. Instead we invoke the route handler
directly and iterate the :class:`EventSourceResponse`'s body iterator;
that is our own async generator, so we can assert the emitted dicts
without the HTTP plumbing.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.events import events
from astro_brain.services.fakes import FakeMount


@pytest.fixture
def wired_bus() -> Iterator[StateBus]:
    bus = StateBus()
    prev = deps.get_bus
    deps.get_bus = lambda: bus
    try:
        yield bus
    finally:
        deps.get_bus = prev


def _fake_request(*, disconnected: bool = False) -> AsyncMock:
    req = AsyncMock()
    req.is_disconnected = AsyncMock(return_value=disconnected)
    return req


async def test_events_emits_snapshot_then_update(wired_bus: StateBus) -> None:
    mount = FakeMount(wired_bus)
    response = await events(_fake_request())
    it = response.body_iterator

    first = await asyncio.wait_for(it.__anext__(), timeout=1.0)
    assert first["event"] == "snapshot"
    snapshot_payload = json.loads(first["data"])
    assert snapshot_payload["overall"] == "green"
    assert snapshot_payload["subsystems"] == {}

    await mount.start()
    second = await asyncio.wait_for(it.__anext__(), timeout=1.0)
    assert second["event"] == "update"
    update_payload = json.loads(second["data"])
    assert update_payload["subsystem"] == "mount"
    assert update_payload["state"]["state"] == "ready"
    assert update_payload["seq"] == 1

    await it.aclose()


async def test_events_stops_streaming_when_client_disconnects(
    wired_bus: StateBus,
) -> None:
    response = await events(_fake_request(disconnected=True))
    it = response.body_iterator

    # with the client already disconnected, the generator should exit
    # before yielding anything (the disconnect check happens per-iteration,
    # before the yield).
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(it.__anext__(), timeout=1.0)
