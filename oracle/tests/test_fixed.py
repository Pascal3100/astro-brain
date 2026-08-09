import math
from datetime import datetime, timezone

from skyfield.api import Loader, Star

from oracle.compute.fixed import project_to_of_date


def test_project_shape_and_ranges(kernel_path) -> None:
    points = [
        ("NGC1976", 83.82, -5.39),   # M42, J2000
        ("star:HIP32349", 101.29, -16.72),  # Sirius, J2000
    ]
    when = datetime(2026, 8, 1, tzinfo=timezone.utc)
    out = project_to_of_date(points, kernel_path, when)
    assert set(out) == {"NGC1976", "star:HIP32349"}
    for ra, dec in out.values():
        assert 0.0 <= ra < 360.0
        assert -90.0 <= dec <= 90.0


def test_project_is_of_date_not_j2000(kernel_path) -> None:
    # of-date must measurably differ from the input J2000 (precession + aberration).
    points = [("NGC1976", 83.82, -5.39)]
    when = datetime(2026, 8, 1, tzinfo=timezone.utc)
    ra_ofdate, _ = project_to_of_date(points, kernel_path, when)["NGC1976"]
    assert abs(ra_ofdate - 83.82) > 1e-3  # ~0.3 deg drift by 2026

    # and it must match a direct skyfield of-date computation for the same Star
    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    star = Star(ra_hours=83.82 / 15.0, dec_degrees=-5.39)
    t = ts.from_datetime(when)
    ra, dec, _ = eph["earth"].at(t).observe(star).apparent().radec(epoch="date")
    assert math.isclose(ra_ofdate, ra.degrees % 360.0, abs_tol=1e-6)
