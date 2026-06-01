"""Tests du VisibilityEnricher (enrichissement alt/az + filtre visible-now)."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.visibility import VisibilityEnricher

_T = datetime(2026, 3, 20, 22, 0, 0, tzinfo=UTC)


def _obj(qid: str, ra: float, dec: float) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid, kind="star", name=qid.split(":")[1],
        ra_deg=ra, dec_deg=dec,
    )


def test_enrich_sets_alt_az_when_gps_fixed():
    enr = VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35), now_utc=lambda: _T,
    )
    out = enr.enrich([_obj("star:a", 100.0, 40.0)], visible_now=False)
    assert out[0].altitude_deg is not None
    assert out[0].azimuth_deg is not None


def test_visible_now_filters_below_horizon():
    enr = VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35), now_utc=lambda: _T,
    )
    objs = [_obj("star:high", 330.0, 45.0), _obj("star:low", 100.0, -85.0)]
    out = enr.enrich(objs, visible_now=True)
    ids = {o.qualified_id for o in out}
    assert "star:low" not in ids
    assert all(o.altitude_deg is not None and o.altitude_deg > 0.0 for o in out)


def test_no_gps_degrades_gracefully():
    enr = VisibilityEnricher(gps_fix=lambda: None, now_utc=lambda: _T)
    objs = [_obj("star:a", 100.0, 40.0), _obj("star:b", 200.0, -85.0)]
    out = enr.enrich(objs, visible_now=True)  # filtre ignoré sans GPS
    assert len(out) == 2
    assert out[0].altitude_deg is None
    assert out[0].azimuth_deg is None
