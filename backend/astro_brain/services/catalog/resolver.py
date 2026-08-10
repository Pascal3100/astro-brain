"""Résolution d'un `id` catalogue en cible GoTo (RA/Dec + kind + nom)."""
from __future__ import annotations

from dataclasses import dataclass

from astro_brain.services.catalog.reference_catalog import ReferenceCatalog


@dataclass(frozen=True)
class ResolvedTarget:
    """Cible GoTo résolue : coordonnées + métadonnées d'affichage."""

    id: str
    kind: str
    name: str
    ra_deg: float
    dec_deg: float
    stale: bool


class TargetResolver:
    """Résout un `id` catalogue en `ResolvedTarget` via `ReferenceCatalog`."""

    def __init__(self, catalog: ReferenceCatalog) -> None:
        """Bind the resolver to the `catalog` it queries."""
        self._catalog = catalog

    async def resolve(self, obj_id: str) -> ResolvedTarget | None:
        """Return the `ResolvedTarget` for `obj_id`, or `None` if unknown."""
        obj = await self._catalog.get_by_qualified_id(obj_id)
        if obj is None:
            return None
        return ResolvedTarget(
            id=obj.qualified_id,
            kind=obj.kind,
            name=obj.name or obj.designation or obj.qualified_id,
            ra_deg=obj.ra_deg,
            dec_deg=obj.dec_deg,
            stale=obj.ephemeris_stale,
        )
