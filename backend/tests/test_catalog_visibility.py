from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.visibility import VisibilityEnricher


def _enricher() -> VisibilityEnricher:
    return VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35),
        now_utc=lambda: datetime(2026, 6, 21, 22, 0, tzinfo=UTC),
    )


def test_stale_object_not_enriched_and_excluded_when_visible_now() -> None:
    stale = CatalogObject(qualified_id="planet:mars", kind="planet", name="Mars",
                          ra_deg=150.0, dec_deg=11.0, ephemeris_stale=True)
    enr = _enricher()
    kept = enr.enrich([stale], visible_now=False)
    assert kept[0].altitude_deg is None
    assert enr.enrich([stale], visible_now=True) == []
