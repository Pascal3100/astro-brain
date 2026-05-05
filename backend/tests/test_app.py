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
    app = build_app(use_hardware=False, db_path_override=":memory:")
    with TestClient(app) as client:
        response = client.get("/state")
        assert response.status_code == 200
        body = response.json()
        assert body["subsystems"]["mount"]["state"] == "ready"
        assert body["subsystems"]["gps"]["state"] == "fix_3d"


def test_app_slew_and_stop_flow_end_to_end() -> None:
    app = build_app(use_hardware=False, db_path_override=":memory:")
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
    app = build_app(use_hardware=False, db_path_override=":memory:")
    async with app.router.lifespan_context(app):
        assert app.state.db is not None
        cursor = await app.state.db.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        await cursor.close()
        assert row is not None
        assert row[0] == 1
