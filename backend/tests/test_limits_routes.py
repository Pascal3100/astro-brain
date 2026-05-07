"""Integration tests for /limits/alt REST routes."""

from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.limits import router


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an in-memory aiosqlite connection with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


def _make_app(db: aiosqlite.Connection) -> FastAPI:
    """Build a minimal FastAPI app wiring the limits router."""
    app = FastAPI()
    app.state.db = db
    app.include_router(router)
    return app


def test_get_returns_404_when_never_set(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.get("/limits/alt")
        assert r.status_code == 404, r.text


def test_put_then_get_round_trip(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.put(
            "/limits/alt",
            json={"min_deg": 5.0, "max_deg": 85.0},
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"min_deg": 5.0, "max_deg": 85.0}

        r2 = client.get("/limits/alt")
        assert r2.status_code == 200, r2.text
        assert r2.json() == {"min_deg": 5.0, "max_deg": 85.0}


def test_put_overwrites_previous(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r1 = client.put(
            "/limits/alt",
            json={"min_deg": 0.0, "max_deg": 90.0},
        )
        assert r1.status_code == 200, r1.text

        r2 = client.put(
            "/limits/alt",
            json={"min_deg": 10.0, "max_deg": 80.0},
        )
        assert r2.status_code == 200, r2.text

        r3 = client.get("/limits/alt")
        assert r3.status_code == 200
        assert r3.json() == {"min_deg": 10.0, "max_deg": 80.0}


def test_put_invalid_range_too_narrow_returns_422(
    db: aiosqlite.Connection,
) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        # Range < 30° → AltLimits validator rejects → FastAPI returns 422.
        r = client.put(
            "/limits/alt",
            json={"min_deg": 10.0, "max_deg": 30.0},
        )
        assert r.status_code == 422, r.text


def test_put_invalid_min_ge_max_returns_422(db: aiosqlite.Connection) -> None:
    app = _make_app(db)
    with TestClient(app) as client:
        r = client.put(
            "/limits/alt",
            json={"min_deg": 80.0, "max_deg": 10.0},
        )
        assert r.status_code == 422, r.text
