"""Integration tests for ``GET /state``."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.state import router
from astro_brain.services.fakes import FakeMount, FakeNetwork


@dataclass
class Harness:
    client: TestClient
    bus: StateBus


@pytest.fixture
def harness() -> Iterator[Harness]:
    bus = StateBus()
    app = FastAPI()
    app.state.bus = bus
    app.include_router(router)
    with TestClient(app) as client:
        yield Harness(client=client, bus=bus)


def test_state_empty_bus(harness: Harness) -> None:
    r = harness.client.get("/state")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"] == {}
    assert body["seq"] == 0
    assert "ts" in body


async def test_state_after_publishes(harness: Harness) -> None:
    mount = FakeMount(harness.bus)
    network = FakeNetwork(harness.bus)
    await mount.start()
    await network.start()
    r = harness.client.get("/state")
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"]["mount"]["state"] == "ready"
    assert body["subsystems"]["network"]["state"] == "client"
    assert body["seq"] == 2
