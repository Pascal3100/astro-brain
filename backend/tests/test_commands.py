"""Integration tests for the REST command routes (/slew /stop /tracking)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.commands import router
from astro_brain.services.fakes import FakeMount, FakeTracking


@dataclass
class Harness:
    client: TestClient
    bus: StateBus


@pytest.fixture
def harness() -> Iterator[Harness]:
    bus = StateBus()
    mount = FakeMount(bus)
    tracking = FakeTracking(bus)

    app = FastAPI()
    app.state.bus = bus
    app.state.mount = mount
    app.state.tracking = tracking
    app.include_router(router)
    with TestClient(app) as client:
        yield Harness(client=client, bus=bus)


def test_slew_returns_ok_and_moves_mount(harness: Harness) -> None:
    r = harness.client.post(
        "/slew", json={"axis": "alt", "direction": "+", "rate": 5}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    mount_state = harness.bus.get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"


def test_slew_rejects_invalid_axis(harness: Harness) -> None:
    r = harness.client.post(
        "/slew", json={"axis": "xx", "direction": "+", "rate": 5}
    )
    assert r.status_code == 422


def test_slew_rejects_rate_out_of_range(harness: Harness) -> None:
    r = harness.client.post(
        "/slew", json={"axis": "alt", "direction": "+", "rate": 10}
    )
    assert r.status_code == 422


def test_stop_without_axis_stops_all(harness: Harness) -> None:
    harness.client.post(
        "/slew", json={"axis": "alt", "direction": "+", "rate": 5}
    )
    harness.client.post(
        "/slew", json={"axis": "az", "direction": "-", "rate": 3}
    )
    r = harness.client.post("/stop", json={})
    assert r.status_code == 200
    mount_state = harness.bus.get_full_state().subsystems["mount"]
    assert mount_state.state == "ready"


def test_stop_with_axis_stops_only_that_axis(harness: Harness) -> None:
    harness.client.post(
        "/slew", json={"axis": "alt", "direction": "+", "rate": 5}
    )
    harness.client.post(
        "/slew", json={"axis": "az", "direction": "-", "rate": 3}
    )
    r = harness.client.post("/stop", json={"axis": "alt"})
    assert r.status_code == 200
    mount_state = harness.bus.get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"
    remaining = [s["axis"] for s in mount_state.details["active_slews"]]
    assert remaining == ["az"]


def test_tracking_toggle(harness: Harness) -> None:
    r = harness.client.post("/tracking", json={"enabled": True})
    assert r.status_code == 200
    assert (
        harness.bus.get_full_state().subsystems["tracking"].state == "sidereal"
    )
    r = harness.client.post("/tracking", json={"enabled": False})
    assert harness.bus.get_full_state().subsystems["tracking"].state == "off"
