from __future__ import annotations

from pathlib import Path

import pytest

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)
from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
from astro_brain.services.catalog.resolver import TargetResolver
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _resolver(tmp_path: Path) -> TargetResolver:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    cat = ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )
    return TargetResolver(cat)


async def test_resolve_fixed(tmp_path: Path) -> None:
    r = await (await _resolver(tmp_path)).resolve("NGC1976")
    assert r is not None and r.kind == "dso" and r.name == "Orion Nebula"
    assert r.ra_deg == pytest.approx(83.82)
    assert r.stale is False


async def test_resolve_ephemeris_interpolated(tmp_path: Path) -> None:
    r = await (await _resolver(tmp_path)).resolve("planet:mars")
    assert r is not None and r.ra_deg == pytest.approx(150.5)


async def test_resolve_unknown_is_none(tmp_path: Path) -> None:
    assert await (await _resolver(tmp_path)).resolve("nope") is None
