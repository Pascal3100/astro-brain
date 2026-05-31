"""Tests du module d'éphéméride pur (conversion RA/Dec → Az/Alt)."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services._ephemeris import (
    Observer,
    sky_az_alt_from_ra_dec,
)


def test_sky_az_alt_zenith_star_is_high():
    obs = Observer(lat_deg=48.0, lon_deg=0.0)
    t = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    az, alt = sky_az_alt_from_ra_dec(ra_deg=0.0, dec_deg=48.0, observer=obs, t_utc=t)
    assert -1.0 <= alt <= 90.0
    assert 0.0 <= az < 360.0


def test_sky_az_alt_below_horizon_is_negative():
    obs = Observer(lat_deg=48.0, lon_deg=2.35)
    t = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
    _, alt = sky_az_alt_from_ra_dec(ra_deg=101.3, dec_deg=-80.0, observer=obs, t_utc=t)
    assert alt < 0.0
