"""Tests for CatalogRegistry dispatch logic."""
from __future__ import annotations

import pytest

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.registry import CatalogRegistry


class _FakeProvider:
    def __init__(self, kind: str, objects: list[CatalogObject]) -> None:
        self.kind = kind
        self._objects = objects
        self.list_calls: list[CatalogFilter] = []

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        self.list_calls.append(filter)
        results = list(self._objects)
        if filter.max_mag is not None:
            results = [o for o in results if o.mag is not None and o.mag <= filter.max_mag]
        return results[filter.offset : filter.offset + filter.limit]

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        for obj in self._objects:
            if obj.qualified_id.split(":", 1)[1] == raw_id:
                return obj
        return None


def _star(qid: str, name: str, mag: float | None) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid,
        kind=qid.split(":", 1)[0],  # type: ignore[arg-type]
        name=name,
        ra_deg=0.0,
        dec_deg=0.0,
        mag=mag,
    )


@pytest.mark.asyncio
async def test_list_all_dispatches_by_kind() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    messier = _FakeProvider("messier", [_star("messier:m31", "Andromeda", 3.4)])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    rows = await reg.list_all(CatalogFilter(kind="star"))

    assert [r.qualified_id for r in rows] == ["star:sirius"]
    assert messier.list_calls == []


@pytest.mark.asyncio
async def test_list_all_unknown_kind_returns_empty() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    rows = await reg.list_all(CatalogFilter(kind="ngc"))

    assert rows == []


@pytest.mark.asyncio
async def test_list_all_no_kind_merges_all_providers_and_sorts_by_mag() -> None:
    stars = _FakeProvider("star", [
        _star("star:sirius", "Sirius", -1.46),
        _star("star:vega", "Vega", 0.03),
    ])
    messier = _FakeProvider("messier", [_star("messier:m31", "Andromeda", 3.4)])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    rows = await reg.list_all(CatalogFilter(limit=10))

    assert [r.name for r in rows] == ["Sirius", "Vega", "Andromeda"]


@pytest.mark.asyncio
async def test_list_all_no_kind_paginates_globally() -> None:
    stars = _FakeProvider("star", [
        _star("star:s1", "S1", 1.0),
        _star("star:s2", "S2", 2.0),
    ])
    messier = _FakeProvider("messier", [
        _star("messier:m1", "M1", 1.5),
        _star("messier:m2", "M2", 2.5),
    ])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    page1 = await reg.list_all(CatalogFilter(limit=2, offset=0))
    page2 = await reg.list_all(CatalogFilter(limit=2, offset=2))

    assert [r.name for r in page1] == ["S1", "M1"]
    assert [r.name for r in page2] == ["S2", "M2"]


@pytest.mark.asyncio
async def test_get_by_qualified_id_dispatches() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    reg = CatalogRegistry({"star": stars})

    obj = await reg.get_by_qualified_id("star:sirius")

    assert obj is not None
    assert obj.name == "Sirius"


@pytest.mark.asyncio
async def test_get_by_qualified_id_invalid_format_returns_none() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    assert await reg.get_by_qualified_id("noprefix") is None


@pytest.mark.asyncio
async def test_get_by_qualified_id_unknown_kind_returns_none() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    assert await reg.get_by_qualified_id("ngc:7000") is None


@pytest.mark.asyncio
async def test_get_by_qualified_id_unknown_id_returns_none() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    reg = CatalogRegistry({"star": stars})

    assert await reg.get_by_qualified_id("star:missing") is None
