"""Tests for the application factory (:func:`build_app`).

These tests exercise the full wiring: fakes are instantiated, ``deps`` is
rebound, the lifespan starts each service (which publishes its initial
state) and launches the orchestrator as a background task, and the REST
routes are reachable against an in-process :class:`TestClient`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from astro_brain.app import build_app


def test_app_starts_with_fakes_and_state_endpoint_responds() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:", sync_on_boot=False)
    with TestClient(app) as client:
        response = client.get("/state")
        assert response.status_code == 200
        body = response.json()
        assert body["subsystems"]["mount"]["state"] == "ready"
        assert body["subsystems"]["gps"]["state"] == "fix_3d"


def test_app_slew_and_stop_flow_end_to_end() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:", sync_on_boot=False)
    with TestClient(app) as client:
        slew = client.post(
            "/slew", json={"axis": "alt", "direction": "+", "rate": 4}
        )
        assert slew.status_code == 200

        mid = client.get("/state")
        assert mid.json()["subsystems"]["mount"]["state"] == "moving"

        stop = client.post("/stop", json={})
        assert stop.status_code == 200

        end = client.get("/state")
        assert end.json()["subsystems"]["mount"]["state"] == "ready"


@pytest.mark.asyncio
async def test_app_initializes_db() -> None:
    """The lifespan opens an aiosqlite connection and runs migrations."""
    app = build_app(use_hardware=False, db_path_override=":memory:", sync_on_boot=False)
    async with app.router.lifespan_context(app):
        assert app.state.db is not None
        cursor = await app.state.db.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        await cursor.close()
        assert row is not None
        assert row[0] >= 2


@pytest.mark.asyncio
async def test_app_wires_alignment_service() -> None:
    """The lifespan installs an AlignmentService idle on app.state."""
    app = build_app(use_hardware=False, db_path_override=":memory:", sync_on_boot=False)
    async with app.router.lifespan_context(app):
        assert app.state.alignment is not None
        assert app.state.alignment.session() is None


def test_build_app_exposes_catalog_and_reference(tmp_path) -> None:
    from astro_brain.app import build_app
    from astro_brain.services.catalog.reference_catalog import ReferenceCatalog

    app = build_app(use_hardware=False, sync_on_boot=False,
                     db_path_override=tmp_path / "state.db")
    with TestClient(app):
        assert isinstance(app.state.catalog_registry, ReferenceCatalog)
        assert app.state.reference_db is not None
        assert app.state.resolver is not None


def test_catalog_objects_route_is_registered(tmp_path) -> None:
    from astro_brain.app import build_app

    app = build_app(use_hardware=False, sync_on_boot=False,
                     db_path_override=tmp_path / "state.db")
    with TestClient(app) as client:
        r = client.get("/catalog/objects")
        assert r.status_code == 200
        body = r.json()
        assert "objects" in body
        assert "count" in body
