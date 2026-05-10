"""Chargement du mini catalogue + sélection candidates pour wizard 3 étoiles.

Astronomie : conversion RA/Dec (J2000, ICRS) → Az/Alt apparent pour un
observateur à `(lat, lon)` à `t_utc`. On utilise une formule LST + sphérique
classique, précision arc-min — largement suffisante pour pré-pointer dans
un champ d'oculaire de ~1°.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import resources

from astro_brain.models.alignment import Star


@dataclass(frozen=True)
class Observer:
    lat_deg: float
    lon_deg: float


@dataclass(frozen=True)
class MountLimits:
    alt_min: float
    alt_max: float
    az_min: float
    az_max: float


def load_catalog() -> list[Star]:
    """Charge le JSON embarqué et renvoie la liste des étoiles."""
    raw = resources.files("astro_brain.services").joinpath(
        "_alignment_stars.json"
    ).read_text()
    return [Star.model_validate(d) for d in json.loads(raw)]


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
    """Greenwich Mean Sidereal Time en degrés (IAU 1982).

    `T₀` est évalué à 0h UT du jour, et l'heure UT du jour est ajoutée
    séparément via le terme `1.00273790935·H`. Mélanger les deux introduit
    un biais systématique d'environ 0.5° en GMST.
    """
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

    Az mesuré depuis le Nord vers l'Est. Alt depuis l'horizon. Précision
    arc-min, sans corrections nutation/aberration/réfraction.
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


def select_candidates(
    observer: Observer,
    t_utc: datetime,
    limits: MountLimits,
    exclude_ids: set[str],
    *,
    min_alt: float = 20.0,
    isolation_deg: float = 5.0,
) -> list[Star]:
    """Renvoie 3 étoiles candidates distribuées ~120° en AZ.

    - filtre alt > min_alt et dans `limits`
    - filtre `exclude_ids`
    - filtre isolation (pas d'autre brillante < `isolation_deg`)
    - sélectionne 3 étoiles maximisant l'écart AZ entre voisines.
    """
    catalog = [s for s in load_catalog() if s.id not in exclude_ids]
    visible: list[tuple[Star, float, float]] = []
    for star in catalog:
        az, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, observer, t_utc)
        if alt < min_alt or alt < limits.alt_min or alt > limits.alt_max:
            continue
        if not (limits.az_min <= az <= limits.az_max):
            continue
        visible.append((star, az, alt))

    # isolation : élimine ceux qui ont un voisin brillant proche (< isolation_deg)
    isolated: list[tuple[Star, float, float]] = []
    for star, az, alt in visible:
        too_close = False
        for other, oaz, oalt in visible:
            if other.id == star.id:
                continue
            d = math.sqrt((az - oaz) ** 2 + (alt - oalt) ** 2)
            if d < isolation_deg:
                too_close = True
                break
        if not too_close:
            isolated.append((star, az, alt))

    if len(isolated) < 3:
        # Fallback : reprendre les visibles, isolation devient un nice-to-have
        isolated = visible

    # Sélection 3 étoiles maximisant la distribution AZ : on tire le triplet
    # dont les écarts cycliques minimisent l'écart à 120°.
    if len(isolated) <= 3:
        return [s for s, _, _ in isolated[:3]]

    best_triplet: list[Star] | None = None
    best_score = float("inf")
    for i in range(len(isolated)):
        for j in range(i + 1, len(isolated)):
            for k in range(j + 1, len(isolated)):
                azs = sorted(
                    [isolated[i][1], isolated[j][1], isolated[k][1]]
                )
                spans = [
                    (azs[1] - azs[0]) % 360.0,
                    (azs[2] - azs[1]) % 360.0,
                    (azs[0] + 360.0 - azs[2]) % 360.0,
                ]
                score = sum((s - 120.0) ** 2 for s in spans)
                if score < best_score:
                    best_score = score
                    best_triplet = [isolated[i][0], isolated[j][0], isolated[k][0]]
    return best_triplet or [s for s, _, _ in isolated[:3]]
