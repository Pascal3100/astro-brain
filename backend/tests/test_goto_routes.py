# backend/tests/test_goto_routes.py
"""Tests /goto : contrat id-only + gardes (reference/unknown/stale/aligned/solar)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.goto import router
from astro_brain.services.catalog.resolver import ResolvedTarget
from astro_brain.services.fakes import FakeMount
from astro_brain.subsystems import SubsystemState


class _Alignment:
    def __init__(self, aligned: bool) -> None:
        self._aligned = aligned

    @property
    def is_aligned(self) -> bool:
        return self._aligned


class _Ref:
    def __init__(self, ready: bool) -> None:
        self.ready = ready


class _Resolver:
    def __init__(self, target: ResolvedTarget | None) -> None:
        self._target = target

    async def resolve(self, obj_id: str) -> ResolvedTarget | None:
        return self._target


def _client(*, aligned=True, ready=True, target=None, in_progress=False):
    bus = StateBus()
    mount = FakeMount(bus)
    if in_progress:
        bus.publish("mount", SubsystemState(
            state="moving", details={"goto_in_progress": True}))
    app = FastAPI()
    app.include_router(router)
    app.state.bus = bus
    app.state.mount = mount
    app.state.alignment = _Alignment(aligned)
    app.state.reference_db = _Ref(ready)
    app.state.resolver = _Resolver(target)
    return TestClient(app), mount


_M42 = ResolvedTarget(id="NGC1976", kind="dso", name="Orion Nebula",
                      ra_deg=83.82, dec_deg=-5.39, stale=False)
_SUN = ResolvedTarget(id="sun", kind="sun", name="Sun", ra_deg=138.0,
                      dec_deg=16.0, stale=False)
_STALE = ResolvedTarget(id="planet:mars", kind="planet", name="Mars",
                        ra_deg=150.0, dec_deg=11.0, stale=True)


def test_goto_ok_calls_mount_with_resolved_coords():
    client, mount = _client(target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 200
    assert mount.goto_calls == [(83.82, -5.39, "Orion Nebula")]


def test_reference_unavailable_409():
    client, mount = _client(ready=False, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "reference_unavailable"
    assert mount.goto_calls == []


def test_unknown_id_404():
    client, _ = _client(target=None)
    r = client.post("/goto", json={"id": "nope"})
    assert r.status_code == 404 and r.json()["detail"] == "unknown_id"


def test_ephemeris_stale_409():
    client, _ = _client(target=_STALE)
    r = client.post("/goto", json={"id": "planet:mars"})
    assert r.status_code == 409 and r.json()["detail"] == "ephemeris_stale"


def test_not_aligned_409():
    client, _ = _client(aligned=False, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "not_aligned"


def test_goto_in_progress_409():
    client, _ = _client(in_progress=True, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "goto_in_progress"


def test_solar_requires_ack():
    client, mount = _client(target=_SUN)
    r = client.post("/goto", json={"id": "sun"})
    assert r.status_code == 409 and r.json()["detail"] == "solar_ack_required"
    assert mount.goto_calls == []
    ok = client.post("/goto", json={"id": "sun", "confirm_solar": True})
    assert ok.status_code == 200
    assert mount.goto_calls == [(138.0, 16.0, "Sun")]


def test_missing_id_422():
    client, _ = _client(target=_M42)
    assert client.post("/goto", json={}).status_code == 422
