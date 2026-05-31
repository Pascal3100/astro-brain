"""Éphéméride pure : conversion RA/Dec (J2000, ICRS) → Az/Alt apparent.

Formule LST + sphérique classique, précision arc-min — sans corrections
nutation/aberration/réfraction. Aucune I/O, testable isolément. Partagée
par le wizard d'alignement et la couche catalogue (visibilité « maintenant »).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observer:
    lat_deg: float
    lon_deg: float


def _julian_date(t_utc: datetime) -> float:
    """JD à partir d'un datetime UTC."""
    y, m = t_utc.year, t_utc.month
    d = (
        t_utc.day
        + (t_utc.hour + (t_utc.minute + t_utc.second / 60.0) / 60.0) / 24.0
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _gmst_deg(t_utc: datetime) -> float:
    """Greenwich Mean Sidereal Time en degrés (IAU 1982)."""
    jd = _julian_date(t_utc)
    jd0 = math.floor(jd - 0.5) + 0.5  # JD à 0h UT du même jour
    h_ut = (jd - jd0) * 24.0           # heures UT depuis 0h
    t0 = (jd0 - 2451545.0) / 36525.0
    gmst_h = (
        6.697374558
        + 2400.051336 * t0
        + 0.000025862 * t0 * t0
        + 1.00273790935 * h_ut
    )
    return (gmst_h * 15.0) % 360.0


def sky_az_alt_from_ra_dec(
    ra_deg: float, dec_deg: float, observer: Observer, t_utc: datetime
) -> tuple[float, float]:
    """Convertit (ra, dec) → (az, alt) pour `observer` à `t_utc`.

    Az mesuré depuis le Nord vers l'Est. Alt depuis l'horizon.
    """
    gmst = _gmst_deg(t_utc)
    lst = (gmst + observer.lon_deg) % 360.0
    ha_deg = (lst - ra_deg) % 360.0
    if ha_deg > 180:
        ha_deg -= 360
    ha = math.radians(ha_deg)
    dec = math.radians(dec_deg)
    lat = math.radians(observer.lat_deg)

    sin_alt = math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(ha)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))

    sin_az = -math.cos(dec) * math.sin(ha) / math.cos(math.radians(alt))
    cos_az = (math.sin(dec) - math.sin(math.radians(alt)) * math.sin(lat)) / (
        math.cos(math.radians(alt)) * math.cos(lat)
    )
    az = math.degrees(math.atan2(sin_az, cos_az)) % 360.0
    return az, alt
