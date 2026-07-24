import math
from datetime import datetime, timezone

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
        assert r.comet_id in set(comets.index)
