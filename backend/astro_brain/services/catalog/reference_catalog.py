"""Façade catalogue au-dessus des providers fixe/éphémère (reference.sqlite)."""
from __future__ import annotations

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)


class ReferenceCatalog:
    """Façade catalogue combinant objets fixes et éphémères de `reference.sqlite`."""

    def __init__(
        self,
        *,
        fixed: FixedObjectProvider,
        ephemeris: EphemerisProvider,
        reference: ReferenceDb,
    ) -> None:
        """Bind the catalog to its providers and the `reference.sqlite` handle."""
        self._fixed = fixed
        self._ephemeris = ephemeris
        self._reference = reference

    async def get_by_qualified_id(self, obj_id: str) -> CatalogObject | None:
        """Return the object identified by `obj_id`, or `None` if not found."""
        if not self._reference.ready:
            return None
        obj = await self._fixed.get_object(obj_id)
        if obj is not None:
            return obj
        return await self._ephemeris.get_object(obj_id)
