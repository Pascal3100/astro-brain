from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)
from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _catalog(tmp_path: Path) -> ReferenceCatalog:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )


async def test_list_all_merges_all_families(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    objs = await cat.list_all(CatalogFilter(limit=100))
    assert {o.kind for o in objs} == {"comet", "planet", "moon", "sun", "dso",
                                      "star"}


async def test_list_all_sorted_by_mag(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    mags = [o.mag for o in await cat.list_all(CatalogFilter(limit=100))
            if o.mag is not None]
    assert mags == sorted(mags)


async def test_get_by_id_routes_fixed_and_ephemeris(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    assert (await cat.get_by_qualified_id("NGC1976")).kind == "dso"
    assert (await cat.get_by_qualified_id("planet:mars")).kind == "planet"
    assert await cat.get_by_qualified_id("bogus:id") is None


async def test_not_ready_yields_empty(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    cat = ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )
    assert await cat.list_all(CatalogFilter()) == []
    assert await cat.get_by_qualified_id("NGC1976") is None
