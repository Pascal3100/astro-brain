# backend/tests/test_fixed_object_provider.py
from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.providers import FixedObjectProvider
from tests.reference_fixtures import build_reference_v2


async def _provider(tmp_path: Path) -> FixedObjectProvider:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return FixedObjectProvider(ref)


async def test_get_object_by_id(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    m42 = await prov.get_object("NGC1976")
    assert m42 is not None and m42.messier == "M42"
    assert m42.angular_size_arcmin == 85.0
    assert await prov.get_object("planet:mars") is None
