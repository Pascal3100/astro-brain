"""Chargement du mini catalogue + sélection candidates pour wizard 3 étoiles."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import resources

from astro_brain.models.alignment import Star
from astro_brain.services._ephemeris import (  # ré-export pour compat
    Observer,
    _gmst_deg,
    sky_az_alt_from_ra_dec,
)

__all__ = [
    "Observer",
    "MountLimits",
    "load_catalog",
    "select_candidates",
    "sky_az_alt_from_ra_dec",
]


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
