"""Tests du module d'éphéméride pur (conversion RA/Dec → Az/Alt)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from astro_brain.services._ephemeris import (
    Observer,
    sky_az_alt_from_ra_dec,
)


def test_meridian_transit_altitude_matches_geometry():
    from astro_brain.services._ephemeris import _gmst_deg

    obs = Observer(lat_deg=48.0, lon_deg=0.0)
    t = datetime(2026, 3, 20, 22, 0, 0, tzinfo=UTC)
    lst = (_gmst_deg(t) + obs.lon_deg) % 360.0
    ra = lst  # angle horaire = 0 → objet au méridien
    az, alt = sky_az_alt_from_ra_dec(ra_deg=ra, dec_deg=40.0, observer=obs, t_utc=t)
    # Au méridien sud (dec < lat) : alt = 90 - (lat - dec) = 82°, az = 180°.
    assert alt == pytest.approx(90.0 - (48.0 - 40.0), abs=0.3)
    assert az == pytest.approx(180.0, abs=0.5)


def test_sky_az_alt_below_horizon_is_negative():
    obs = Observer(lat_deg=48.0, lon_deg=2.35)
    t = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
    _, alt = sky_az_alt_from_ra_dec(ra_deg=101.3, dec_deg=-80.0, observer=obs, t_utc=t)
    assert alt < 0.0
