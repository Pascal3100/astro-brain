import math
from datetime import datetime, timezone

import pandas as pd
from skyfield.api import Loader
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from oracle.compute.ephemeris import (
    compute_ephemeris,
    predicted_magnitude,
)
from oracle.sources.comets import load_comets


def test_predicted_magnitude_formula() -> None:
    # m = g + 5*log10(delta) + 2.5*k*log10(r)
    m = predicted_magnitude(g=5.0, k=4.0, earth_dist_au=1.0, sun_dist_au=1.0)
    assert m == 5.0  # log10(1) == 0
    m2 = predicted_magnitude(g=5.0, k=4.0, earth_dist_au=10.0, sun_dist_au=1.0)
    assert math.isclose(m2, 5.0 + 5.0, rel_tol=1e-9)


def test_compute_ephemeris_shape_and_ranges(kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=5)
    # 3 comets x 5 daily samples
    assert len(rows) == 15
    for r in rows:
        assert 0.0 <= r.ra_deg < 360.0
        assert -90.0 <= r.dec_deg <= 90.0
        assert r.earth_dist_au > 0.0
        assert r.sun_dist_au > 0.0
        assert r.object_id in set(comets.index)
        assert r.sample_utc.endswith("Z")


def test_ephemeris_ra_dec_are_apparent_of_date(kernel_path, fallback_comets_path) -> None:
    # Guards against reverting `.apparent().radec(epoch="date")` back to a
    # bare `astrometric.radec()` (ICRF/J2000), which would silently pass the
    # shape/range assertions above but return positions off by precession +
    # aberration (here ~0.3 deg RA) — enough to matter for framing/GoTo.
    comets = load_comets(fallback_comets_path).head(1)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    row = compute_ephemeris(comets, kernel_path, start, days=1)[0]

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    comet_row = comets.iloc[0]
    comet = eph["sun"] + mpc.comet_orbit(comet_row, ts, GM_SUN)
    astrometric = eph["earth"].at(ts.from_datetime(start)).observe(comet)
    ra_app, dec_app, _ = astrometric.apparent().radec(epoch="date")
    ra_j2000, dec_j2000, _ = astrometric.radec()

    assert math.isclose(row.ra_deg, ra_app.degrees % 360.0, abs_tol=1e-6)
    assert math.isclose(row.dec_deg, dec_app.degrees, abs_tol=1e-6)
    # The two epochs must measurably differ, otherwise this test can't tell
    # apart of-date from J2000 and doesn't actually guard the epoch choice.
    assert abs(ra_app.degrees - ra_j2000.degrees) > 1e-4


def test_ephemeris_missing_magnitude_yields_none(kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(1).copy()
    comets["magnitude_g"] = float("nan")
    comets["magnitude_k"] = float("nan")
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=1)
    assert len(rows) == 1
    assert rows[0].apparent_mag is None
