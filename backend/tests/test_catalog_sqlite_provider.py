"""Tests for SqliteCatalogProvider."""
from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import SqliteCatalogProvider


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        yield conn
    finally:
        await conn.close()


async def _insert(
    db: aiosqlite.Connection,
    *,
    qid: str,
    kind: str,
    name: str,
    designation: str | None = None,
    ra: float = 0.0,
    dec: float = 0.0,
    mag: float | None = None,
    constellation: str | None = None,
    object_type: str | None = None,
    angular_size_arcmin: float | None = None,
    extras_json: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO catalog_objects "
        "(id, kind, name, designation, ra_deg, dec_deg, mag, constellation, "
        "object_type, angular_size_arcmin, extras_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (qid, kind, name, designation, ra, dec, mag, constellation,
         object_type, angular_size_arcmin, extras_json),
    )
    await db.commit()


async def test_list_objects_filters_by_kind(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    await _insert(db, qid="messier:m31", kind="messier", name="Andromeda", mag=3.4)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter())

    assert len(rows) == 1
    assert rows[0].qualified_id == "star:sirius"
    assert rows[0].kind == "star"


async def test_list_objects_filters_by_max_mag(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    await _insert(db, qid="star:vega", kind="star", name="Vega", mag=0.03)
    await _insert(db, qid="star:dim", kind="star", name="Dim", mag=4.5)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter(max_mag=1.0))

    names = {r.name for r in rows}
    assert names == {"Sirius", "Vega"}


async def test_list_objects_filters_by_search_on_name_and_designation(
    db: aiosqlite.Connection,
) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius",
                  designation="α CMa", mag=-1.46)
    await _insert(db, qid="star:rigel", kind="star", name="Rigel",
                  designation="β Ori", mag=0.13)
    provider = SqliteCatalogProvider(db, kind="star")

    by_name = await provider.list_objects(CatalogFilter(search="rig"))
    assert {r.name for r in by_name} == {"Rigel"}

    by_designation = await provider.list_objects(CatalogFilter(search="CMa"))
    assert {r.name for r in by_designation} == {"Sirius"}


async def test_list_objects_orders_by_mag_then_name(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:b", kind="star", name="B", mag=2.0)
    await _insert(db, qid="star:a", kind="star", name="A", mag=2.0)
    await _insert(db, qid="star:c", kind="star", name="C", mag=1.0)
    await _insert(db, qid="star:nullmag", kind="star", name="NullMag", mag=None)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter())

    # mag asc (NULLS LAST), then name asc
    assert [r.name for r in rows] == ["C", "A", "B", "NullMag"]


async def test_list_objects_limit_offset(db: aiosqlite.Connection) -> None:
    for i in range(5):
        await _insert(db, qid=f"star:s{i}", kind="star", name=f"S{i}", mag=float(i))
    provider = SqliteCatalogProvider(db, kind="star")

    page1 = await provider.list_objects(CatalogFilter(limit=2, offset=0))
    page2 = await provider.list_objects(CatalogFilter(limit=2, offset=2))

    assert [r.name for r in page1] == ["S0", "S1"]
    assert [r.name for r in page2] == ["S2", "S3"]


async def test_get_object_strips_kind_prefix(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.qualified_id == "star:sirius"
    assert obj.name == "Sirius"


async def test_get_object_returns_none_when_absent(db: aiosqlite.Connection) -> None:
    provider = SqliteCatalogProvider(db, kind="star")
    assert await provider.get_object("missing") is None


async def test_get_object_does_not_cross_kind(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="messier:m31", kind="messier", name="Andromeda", mag=3.4)
    provider = SqliteCatalogProvider(db, kind="star")

    assert await provider.get_object("m31") is None


async def test_extras_json_parsed_to_dict(db: aiosqlite.Connection) -> None:
    await _insert(
        db,
        qid="star:sirius",
        kind="star",
        name="Sirius",
        mag=-1.46,
        extras_json='{"spectral_type": "A1V"}',
    )
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.extras == {"spectral_type": "A1V"}


async def test_extras_json_null_yields_empty_dict(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.extras == {}
