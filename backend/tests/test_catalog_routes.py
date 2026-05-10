"""Tests for /catalog/objects routes."""
from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.routes.catalog import router
from astro_brain.services.catalog.models import CatalogObject


def _build_client(registry) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.catalog_registry = registry
    return TestClient(app)


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
