"""Tests du router /goto (garde is_aligned + goto_in_progress + validation)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.goto import router
from astro_brain.services.fakes import FakeMount
from astro_brain.subsystems import SubsystemState


class _Alignment:
    def __init__(self, aligned: bool) -> None:
        self._aligned = aligned

    @property
    def is_aligned(self) -> bool:
        return self._aligned

    def invalidate(self) -> None:  # pragma: no cover
        self._aligned = False


def _client(*, aligned: bool) -> tuple[TestClient, FakeMount, StateBus]:
    bus = StateBus()
    mount = FakeMount(bus)
    app = FastAPI()
    app.include_router(router)
    app.state.bus = bus
    app.state.mount = mount
    app.state.alignment = _Alignment(aligned)
    return TestClient(app), mount, bus


def test_goto_blocked_when_not_aligned():
    client, mount, _ = _client(aligned=False)
    resp = client.post("/goto", json={"ra_deg": 101.0, "dec_deg": -16.0,
                                      "target_name": "Sirius"})
    assert resp.status_code == 409
    assert mount.goto_calls == []


def test_goto_ok_when_aligned_calls_mount():
    client, mount, _ = _client(aligned=True)
    resp = client.post("/goto", json={"ra_deg": 101.287, "dec_deg": -16.716,
                                      "target_name": "Sirius"})
    assert resp.status_code == 200
    assert mount.goto_calls == [(101.287, -16.716, "Sirius")]


def test_goto_blocked_when_already_in_progress():
    client, mount, bus = _client(aligned=True)
    bus.publish("mount", SubsystemState(
        state="moving", details={"goto_in_progress": True}))
    resp = client.post("/goto", json={"ra_deg": 10.0, "dec_deg": 10.0})
    assert resp.status_code == 409


def test_goto_invalid_coords_422():
    client, _, _ = _client(aligned=True)
    resp = client.post("/goto", json={"ra_deg": 999.0, "dec_deg": 200.0})
    assert resp.status_code == 422
