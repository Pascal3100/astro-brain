"""Enrichissement de visibilité pour le catalogue.

Calcule l'altitude/azimut courants de chaque objet pour l'observateur
(position GPS) à l'instant présent, et filtre optionnellement les objets
sous l'horizon. Sans fix GPS, dégrade gracieusement : ne renseigne pas
alt/az et ignore le filtre.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from astro_brain.services._ephemeris import Observer, sky_az_alt_from_ra_dec
from astro_brain.services.catalog.models import CatalogObject

# Horizon géométrique. Un seuil pratique (obstruction) viendra du Setup tube.
_MIN_VISIBLE_ALT_DEG = 0.0


class VisibilityEnricher:
    """Ajoute alt/az courants aux objets et applique le filtre visible-now."""

    def __init__(
        self,
        *,
        gps_fix: Callable[[], tuple[float, float] | None],
        now_utc: Callable[[], datetime],
    ) -> None:
        self._gps_fix = gps_fix
        self._now_utc = now_utc

    def enrich(
        self, objects: list[CatalogObject], *, visible_now: bool
    ) -> list[CatalogObject]:
        fix = self._gps_fix()
        if fix is None:
            # Pas de position : on ne peut rien calculer. Filtre ignoré.
            return objects
        observer = Observer(lat_deg=fix[0], lon_deg=fix[1])
        t = self._now_utc()
        enriched: list[CatalogObject] = []
        for obj in objects:
            az, alt = sky_az_alt_from_ra_dec(obj.ra_deg, obj.dec_deg, observer, t)
            if visible_now and alt <= _MIN_VISIBLE_ALT_DEG:
                continue
            enriched.append(
                obj.model_copy(update={"altitude_deg": alt, "azimuth_deg": az})
            )
        return enriched
