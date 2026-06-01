"""Tests for /catalog/objects routes."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.catalog import router
from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.providers import SqliteCatalogProvider
from astro_brain.services.catalog.registry import CatalogRegistry
from astro_brain.services.catalog.visibility import VisibilityEnricher


def _build_client(registry) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.catalog_registry = registry
    app.state.visibility_enricher = VisibilityEnricher(
        gps_fix=lambda: None,
        now_utc=lambda: datetime.now(UTC),
    )
    return TestClient(app)


@pytest.fixture()
async def visibility_db() -> AsyncIterator[aiosqlite.Connection]:
    """In-memory DB migrated and seeded with one above-horizon star (Vega)."""
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    # Vega: ra=279.23°, dec=+38.78° — above horizon from Paris on 2026-06-21 22:00 UTC
    await conn.execute(
        "INSERT INTO catalog_objects"
        " (id, kind, name, designation, ra_deg, dec_deg, mag,"
        "  constellation, object_type, angular_size_arcmin, extras_json)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("star:vega", "star", "Vega", "α Lyr", 279.23, 38.78, 0.03,
         "Lyr", "star", None, "{}"),
    )
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


def _star(qid: str, name: str, mag: float | None = 1.0) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid,
        kind="star",
        name=name,
        ra_deg=0.0,
        dec_deg=0.0,
        mag=mag,
    )


def test_list_objects_returns_paginated_envelope() -> None:
    registry = AsyncMock()
    registry.list_all = AsyncMock(return_value=[_star("star:sirius", "Sirius", -1.46)])
    client = _build_client(registry)

    r = client.get("/catalog/objects")

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert body["objects"][0]["qualified_id"] == "star:sirius"
    assert body["objects"][0]["extras"] == {}


def test_list_objects_propagates_query_params() -> None:
    registry = AsyncMock()
    registry.list_all = AsyncMock(return_value=[])
    client = _build_client(registry)

    r = client.get(
        "/catalog/objects",
        params={"kind": "star", "search": "sir", "max_mag": 1.0,
                "limit": 25, "offset": 10},
    )

    assert r.status_code == 200
    registry.list_all.assert_awaited_once()
    f = registry.list_all.await_args.args[0]
    assert f.kind == "star"
    assert f.search == "sir"
    assert f.max_mag == 1.0
    assert f.limit == 25
    assert f.offset == 10


def test_list_objects_rejects_limit_above_500() -> None:
    registry = AsyncMock()
    client = _build_client(registry)

    r = client.get("/catalog/objects", params={"limit": 501})

    assert r.status_code == 422


def test_list_objects_rejects_negative_offset() -> None:
    registry = AsyncMock()
    client = _build_client(registry)

    r = client.get("/catalog/objects", params={"offset": -1})

    assert r.status_code == 422


def test_get_object_returns_200_when_found() -> None:
    registry = AsyncMock()
    registry.get_by_qualified_id = AsyncMock(
        return_value=_star("star:sirius", "Sirius", -1.46)
    )
    client = _build_client(registry)

    r = client.get("/catalog/objects/star:sirius")

    assert r.status_code == 200
    assert r.json()["name"] == "Sirius"


def test_get_object_returns_404_when_absent() -> None:
    registry = AsyncMock()
    registry.get_by_qualified_id = AsyncMock(return_value=None)
    client = _build_client(registry)

    r = client.get("/catalog/objects/star:missing")

    assert r.status_code == 404


async def test_visible_now_enriches_altitude_deg(
    visibility_db: aiosqlite.Connection,
) -> None:
    """GET /catalog/objects?visible_now=true must return altitude_deg > 0 for Vega."""
    # Fixed observer: Paris, summer solstice 22:00 UTC — Vega is well above horizon
    _OBSERVER_GPS: tuple[float, float] = (48.0, 2.35)
    _NOW = datetime(2026, 6, 21, 22, 0, 0, tzinfo=UTC)

    app = FastAPI()
    app.include_router(router)
    app.state.catalog_registry = CatalogRegistry({
        "star": SqliteCatalogProvider(visibility_db, kind="star"),
    })
    app.state.visibility_enricher = VisibilityEnricher(
        gps_fix=lambda: _OBSERVER_GPS,
        now_utc=lambda: _NOW,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        r = await ac.get("/catalog/objects", params={"visible_now": "true"})

    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1, "Vega should be visible"
    for obj in body["objects"]:
        assert obj["altitude_deg"] is not None, f"{obj['name']} missing altitude_deg"
        assert obj["altitude_deg"] > 0.0, (
            f"{obj['name']} altitude_deg={obj['altitude_deg']} should be > 0"
        )
