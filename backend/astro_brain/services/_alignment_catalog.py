"""Chargement du mini catalogue + sélection candidates pour wizard 3 étoiles."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import resources

from astro_brain.models.alignment import Star
from astro_brain.services._ephemeris import (
    Observer,
    sky_az_alt_from_ra_dec,
)

__all__ = [
    "Observer",
    "MountLimits",
    "load_catalog",
    "select_candidates",
    "sky_az_alt_from_ra_dec",
    "constellation_of",
    "visible_stars",
]


# Abréviations IAU officielles : 3 lettres, première en majuscule.
_IAU_ABBRS = frozenset({
    "And", "Ant", "Aps", "Aqr", "Aql", "Ara", "Ari", "Aur", "Boo", "Cae",
    "Cam", "Cnc", "CVn", "CMa", "CMi", "Cap", "Car", "Cas", "Cen", "Cep",
    "Cet", "Cha", "Cir", "Col", "Com", "CrA", "CrB", "Crv", "Crt", "Cru",
    "Cyg", "Del", "Dor", "Dra", "Equ", "Eri", "For", "Gem", "Gru", "Her",
    "Hor", "Hya", "Hyi", "Ind", "Lac", "Leo", "LMi", "Lep", "Lib", "Lup",
    "Lyn", "Lyr", "Men", "Mic", "Mon", "Mus", "Nor", "Oct", "Oph", "Ori",
    "Pav", "Peg", "Per", "Phe", "Pic", "Psc", "PsA", "Pup", "Pyx", "Ret",
    "Sge", "Sgr", "Sco", "Scl", "Sct", "Ser", "Sex", "Tau", "Tel", "Tri",
    "TrA", "Tuc", "UMa", "UMi", "Vel", "Vir", "Vol", "Vul",
})


def constellation_of(star: Star) -> str | None:
    """Dérive l'abréviation IAU (3 lettres) depuis le champ `bayer`.

    Le bayer est de la forme « <lettre/numéro> <Abbr> » (ex. « α CMa »,
    « 51 Peg »). On lit le dernier token. Renvoie None si non reconnu.
    """
    parts = star.bayer.split()
    if not parts:
        return None
    abbr = parts[-1]
    return abbr if abbr in _IAU_ABBRS else None


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


def visible_stars(
    observer: Observer,
    t_utc: datetime,
    limits: MountLimits,
    *,
    min_alt: float = 20.0,
) -> dict[str, list[tuple[Star, float, float]]]:
    """Étoiles d'alignement actuellement pointables, groupées par constellation.

    Filtre alt > min_alt et dans `limits` (mêmes critères que
    `select_candidates`). Renvoie {abbr_IAU: [(star, az, alt), ...]} trié par
    magnitude croissante dans chaque groupe.
    """
    groups: dict[str, list[tuple[Star, float, float]]] = {}
    for star in load_catalog():
        az, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, observer, t_utc)
        if alt < min_alt or alt < limits.alt_min or alt > limits.alt_max:
            continue
        if not (limits.az_min <= az <= limits.az_max):
            continue
        abbr = constellation_of(star)
        if abbr is None:
            continue
        groups.setdefault(abbr, []).append((star, az, alt))
    for entries in groups.values():
        entries.sort(key=lambda e: e[0].mag)
    return groups
