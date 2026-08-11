from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.providers import EphemerisProvider
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _provider(tmp_path: Path, now: datetime = FIX_NOW) -> EphemerisProvider:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return EphemerisProvider(ref, now_utc=lambda: now)


async def test_get_object_interpolates_in_window(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    mars = await prov.get_object("planet:mars")
    assert mars is not None
    assert mars.ra_deg == pytest.approx(150.5)   # interpolé à 09 12:00
    assert mars.dec_deg == pytest.approx(11.5)
    assert mars.ephemeris_stale is False


async def test_get_object_moon_has_illumination(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    moon = await prov.get_object("moon")
    assert moon is not None and moon.illumination is not None


async def test_get_object_out_of_window_is_stale(tmp_path: Path) -> None:
    far = datetime(2027, 1, 1, tzinfo=UTC)
    prov = await _provider(tmp_path, now=far)
    mars = await prov.get_object("planet:mars")
    assert mars is not None and mars.ephemeris_stale is True


async def test_get_object_unknown_id_is_none(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    assert await prov.get_object("star:HIP91262") is None
