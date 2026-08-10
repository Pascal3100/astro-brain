# backend/tests/test_fixed_object_provider.py
from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import FixedObjectProvider
from tests.reference_fixtures import build_reference_v2


async def _provider(tmp_path: Path) -> FixedObjectProvider:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return FixedObjectProvider(ref)


async def test_lists_dso_and_star(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter())
    kinds = {o.kind for o in objs}
    assert kinds == {"dso", "star"}
    vega = next(o for o in objs if o.name == "Vega")
    assert vega.qualified_id == "star:HIP91262"
    assert vega.mag == 0.03


async def test_filter_kind_dso_only(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(kind="dso"))
    assert [o.kind for o in objs] == ["dso"]


async def test_messier_only(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(messier_only=True))
    assert all(o.messier is not None for o in objs)
    assert any(o.messier == "M42" for o in objs)


async def test_max_mag_filters_faint(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(max_mag=1.0))
    assert all(o.mag is not None and o.mag <= 1.0 for o in objs)
    assert {o.name for o in objs} == {"Vega"}


async def test_get_object_by_id(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    m42 = await prov.get_object("NGC1976")
    assert m42 is not None and m42.messier == "M42"
    assert m42.angular_size_arcmin == 85.0
    assert await prov.get_object("planet:mars") is None
