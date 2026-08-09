"""Compute daily apparent (of-date) comet ephemeris with skyfield."""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from skyfield.api import Loader, load_constellation_map, position_of_radec
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from oracle.records import EphemRow

__all__ = ["EphemRow", "predicted_magnitude", "compute_ephemeris"]


def predicted_magnitude(
    g: float, k: float, earth_dist_au: float, sun_dist_au: float
) -> float:
    """Total comet magnitude: m = g + 5*log10(delta) + 2.5*k*log10(r)."""
    return g + 5.0 * math.log10(earth_dist_au) + 2.5 * k * math.log10(sun_dist_au)


def compute_ephemeris(
    comets: pd.DataFrame,
    kernel_path: Path,
    start_utc: datetime,
    days: int = 60,
) -> list[EphemRow]:
    """Daily apparent RA/Dec (of-date) for each comet over ``days`` days."""
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    else:
        start_utc = start_utc.astimezone(timezone.utc)

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    sun, earth = eph["sun"], eph["earth"]
    constellation_at = load_constellation_map()

    rows: list[EphemRow] = []
    for designation, row in comets.iterrows():
        comet = sun + mpc.comet_orbit(row, ts, GM_SUN)
        g = row.get("magnitude_g")
        k = row.get("magnitude_k")
        for day in range(days):
            when = start_utc + timedelta(days=day)
            t = ts.from_datetime(when)
            astrometric = earth.at(t).observe(comet)
            ra, dec, delta = astrometric.apparent().radec(epoch="date")
            r = sun.at(t).observe(comet).distance()
            mag = (
                predicted_magnitude(float(g), float(k), delta.au, r.au)
                if pd.notna(g) and pd.notna(k)
                else None
            )
            try:
                const = constellation_at(position_of_radec(ra.hours, dec.degrees))
            except Exception:
                const = None
            rows.append(
                EphemRow(
                    object_id=str(designation),
                    sample_utc=when.isoformat().replace("+00:00", "Z"),
                    ra_deg=ra.degrees % 360.0,
                    dec_deg=dec.degrees,
                    earth_dist_au=delta.au,
                    sun_dist_au=r.au,
                    apparent_mag=mag,
                    illumination=None,
                    constellation=const,
                )
            )
    return rows
