"""Project fixed-object positions from J2000 to apparent of-date (JNow)."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from skyfield.api import Loader, Star

__all__ = ["project_to_of_date"]


def project_to_of_date(
    points: list[tuple[str, float, float]],
    kernel_path: Path,
    when_utc: datetime,
) -> dict[str, tuple[float, float]]:
    """Map each ``(id, ra_deg_j2000, dec_deg_j2000)`` to ``(ra_deg, dec_deg)`` of-date.

    Vectorised: one instant, N objects. Consumers never do precession/nutation,
    so the artifact stores JNow positions computed here at generation time.
    """
    if not points:
        return {}
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    else:
        when_utc = when_utc.astimezone(timezone.utc)

    ids = [p[0] for p in points]
    ra_hours = np.array([p[1] / 15.0 for p in points])
    dec_degrees = np.array([p[2] for p in points])

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    earth = eph["earth"]
    t = ts.from_datetime(when_utc)

    star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
    ra, dec, _ = earth.at(t).observe(star).apparent().radec(epoch="date")
    return {
        i: (float(r) % 360.0, float(d))
        for i, r, d in zip(ids, ra.degrees, dec.degrees)
    }
