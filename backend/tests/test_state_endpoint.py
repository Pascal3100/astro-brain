"""Integration tests for ``GET /state``."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.state import router
from astro_brain.services.fakes import FakeGps, FakeMount


@pytest.fixture
def client() -> Iterator[TestClient]:
    bus = StateBus()
    prev = deps.get_bus
    deps.get_bus = lambda: bus
    app = FastAPI()
    app.include_router(router)
    try:
        yield TestClient(app)
    finally:
        deps.get_bus = prev


def test_state_empty_bus(client: TestClient) -> None:
    r = client.get("/state")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"] == {}
    assert body["seq"] == 0
    assert "ts" in body


async def test_state_after_publishes(client: TestClient) -> None:
    bus = deps.get_bus()
    mount = FakeMount(bus)
    gps = FakeGps(bus)
    await mount.start()
    await gps.start()
    r = client.get("/state")
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"]["mount"]["state"] == "ready"
    assert body["subsystems"]["gps"]["state"] == "fix_3d"
    assert body["seq"] == 2
