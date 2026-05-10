"""Smoke test: the real committed seed_stars.sql loads correctly."""
from __future__ import annotations

from collections.abc import AsyncIterator
from importlib.resources import as_file, files

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import SqliteCatalogProvider
from astro_brain.services.catalog.seed_runner import apply_seeds


@pytest.fixture
async def db_with_seeds() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        with as_file(files("astro_brain.data")) as data_dir:
            await apply_seeds(conn, data_dir)
        yield conn
    finally:
        await conn.close()


async def test_seed_stars_loads_at_least_50_entries(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    cursor = await db_with_seeds.execute(
        "SELECT COUNT(*) FROM catalog_objects WHERE kind = 'star'"
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] >= 50


async def test_seed_stars_contains_iconic_entries(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    provider = SqliteCatalogProvider(db_with_seeds, kind="star")

    sirius = await provider.get_object("sirius")
    vega = await provider.get_object("vega")
    polaris = await provider.get_object("polaris")

    assert sirius is not None and sirius.name == "Sirius"
    assert vega is not None and vega.name == "Vega"
    assert polaris is not None and polaris.name == "Polaris"


async def test_seed_stars_has_valid_coordinates(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    cursor = await db_with_seeds.execute(
        "SELECT id, ra_deg, dec_deg FROM catalog_objects WHERE kind = 'star'"
    )
    rows = await cursor.fetchall()
    await cursor.close()
    for qid, ra, dec in rows:
        assert 0.0 <= ra < 360.0, f"{qid}: ra={ra}"
        assert -90.0 <= dec <= 90.0, f"{qid}: dec={dec}"


async def test_seed_stars_max_mag_filter_works(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    provider = SqliteCatalogProvider(db_with_seeds, kind="star")

    bright = await provider.list_objects(CatalogFilter(max_mag=2.0, limit=500))

    assert len(bright) >= 10
    for obj in bright:
        assert obj.mag is not None and obj.mag <= 2.0
