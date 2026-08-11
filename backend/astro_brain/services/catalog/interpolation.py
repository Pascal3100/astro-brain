"""Interpolation linéaire pure des éphémères (RA/Dec à un instant donné).

Aucune I/O. Les échantillons sont journaliers ; on interpole linéairement
entre les deux qui encadrent l'instant, en prenant le plus court arc pour le
RA (gère 359°→1° sans téléporter). Utilisé par le provider éphémère
(`providers.py`) — `resolver.py` ne dépend pas de ce module, il interroge
directement `ReferenceCatalog`.
"""
from __future__ import annotations

from datetime import UTC, datetime


def parse_utc(s: str) -> datetime:
    """Parse un ISO-8601 (suffixe ``Z`` accepté) en datetime tz-aware UTC."""
    text = s.replace("Z", "+00:00") if s.endswith("Z") else s
    t = datetime.fromisoformat(text)
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def lerp(a: float, b: float, frac: float) -> float:
    """Interpole linéairement entre ``a`` et ``b`` à la fraction ``frac``."""
    return a + (b - a) * frac


def lerp_angle_deg(a: float, b: float, frac: float) -> float:
    """Interpole un angle (deg) sur le plus court arc ; résultat dans [0, 360)."""
    diff = ((b - a + 180.0) % 360.0) - 180.0
    return (a + diff * frac) % 360.0


def interpolate_radec(
    before: tuple[datetime, float, float],
    after: tuple[datetime, float, float],
    t: datetime,
) -> tuple[float, float]:
    """Interpole (ra, dec) à ``t`` entre deux échantillons ``(utc, ra, dec)``."""
    t0, ra0, dec0 = before
    t1, ra1, dec1 = after
    span = (t1 - t0).total_seconds()
    if span == 0:
        return ra0 % 360.0, dec0
    frac = (t - t0).total_seconds() / span
    frac = max(0.0, min(1.0, frac))
    return lerp_angle_deg(ra0, ra1, frac), lerp(dec0, dec1, frac)
