"""Integration tests for the REST command routes (/slew /stop /tracking)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.commands import router
from astro_brain.services.fakes import FakeMount, FakeTracking


@pytest.fixture
def client() -> Iterator[TestClient]:
    bus = StateBus()
    mount = FakeMount(bus)
    tracking = FakeTracking(bus)

    # remember previous wiring to restore it at teardown so tests don't leak
    prev = (deps.get_bus, deps.get_mount, deps.get_tracking)
    deps.get_bus = lambda: bus
    deps.get_mount = lambda: mount
    deps.get_tracking = lambda: tracking

    app = FastAPI()
    app.include_router(router)
    try:
        yield TestClient(app)
    finally:
        deps.get_bus, deps.get_mount, deps.get_tracking = prev


def test_slew_returns_ok_and_moves_mount(client: TestClient) -> None:
    r = client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"


def test_slew_rejects_invalid_axis(client: TestClient) -> None:
    r = client.post("/slew", json={"axis": "xx", "direction": "+", "rate": 5})
    assert r.status_code == 422


def test_slew_rejects_rate_out_of_range(client: TestClient) -> None:
    r = client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 10})
    assert r.status_code == 422


def test_stop_without_axis_stops_all(client: TestClient) -> None:
    client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    client.post("/slew", json={"axis": "az", "direction": "-", "rate": 3})
    r = client.post("/stop", json={})
    assert r.status_code == 200
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "ready"


def test_stop_with_axis_stops_only_that_axis(client: TestClient) -> None:
    client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    client.post("/slew", json={"axis": "az", "direction": "-", "rate": 3})
    r = client.post("/stop", json={"axis": "alt"})
    assert r.status_code == 200
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"
    remaining = [s["axis"] for s in mount_state.details["active_slews"]]
    assert remaining == ["az"]


def test_tracking_toggle(client: TestClient) -> None:
    r = client.post("/tracking", json={"enabled": True})
    assert r.status_code == 200
    assert (
        deps.get_bus().get_full_state().subsystems["tracking"].state
        == "sidereal"
    )
    r = client.post("/tracking", json={"enabled": False})
    assert (
        deps.get_bus().get_full_state().subsystems["tracking"].state == "off"
    )
