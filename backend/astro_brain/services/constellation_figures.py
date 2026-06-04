"""Chargement de l'asset des figures + rendu (matching cible + alt/az).

Le matching de l'étoile cible se fait par proximité angulaire (robuste aux
divergences de désignation entre l'étoile d'alignement et le nœud de figure).
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from importlib import resources

from astro_brain.services._ephemeris import Observer, sky_az_alt_from_ra_dec

__all__ = ["load_figures", "figure_for", "render_figure"]

_TARGET_MATCH_DEG = 1.0  # tolérance de matching cible
_FIGURES: dict[str, dict] | None = None


def load_figures() -> dict[str, dict]:
    """Charge l'asset des figures (une seule fois, mis en cache module)."""
    global _FIGURES
    if _FIGURES is None:
        raw = resources.files("astro_brain.data").joinpath(
            "constellation_figures.json"
        ).read_text(encoding="utf-8")
        _FIGURES = json.loads(raw)
    return _FIGURES


def figure_for(abbr: str) -> dict | None:
    return load_figures().get(abbr)


def _angular_sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cos_sep = (math.sin(d1) * math.sin(d2)
               + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))


def render_figure(
    figure: dict,
    *,
    target_ra: float,
    target_dec: float,
    observer: Observer | None,
    t_utc: datetime | None,
) -> dict:
    """Renvoie {name, oriented, nodes:[{label,mag,ra_deg,dec_deg,az,alt,is_target}], segments}.

    - ``is_target`` posé sur le nœud le plus proche de (target_ra, target_dec)
      si < _TARGET_MATCH_DEG, sinon aucun.
    - alt/az calculés si observer/t_utc fournis, sinon None (oriented=False).
    """
    oriented = observer is not None and t_utc is not None
    best_i, best_sep = -1, _TARGET_MATCH_DEG
    for i, node in enumerate(figure["nodes"]):
        sep = _angular_sep_deg(target_ra, target_dec,
                               node["ra_deg"], node["dec_deg"])
        if sep < best_sep:
            best_i, best_sep = i, sep

    nodes = []
    for i, node in enumerate(figure["nodes"]):
        az = alt = None
        if oriented:
            az, alt = sky_az_alt_from_ra_dec(
                node["ra_deg"], node["dec_deg"], observer, t_utc)
        nodes.append({
            "label": node["label"], "mag": node["mag"],
            "ra_deg": node["ra_deg"], "dec_deg": node["dec_deg"],
            "az": az, "alt": alt, "is_target": i == best_i,
        })
    return {"name": figure["name"], "oriented": oriented,
            "nodes": nodes, "segments": figure["segments"]}
