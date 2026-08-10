"""Façade catalogue au-dessus des providers fixe/éphémère (reference.sqlite)."""
from __future__ import annotations

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)


class ReferenceCatalog:
    def __init__(
        self,
        *,
        fixed: FixedObjectProvider,
        ephemeris: EphemerisProvider,
        reference: ReferenceDb,
    ) -> None:
        self._fixed = fixed
        self._ephemeris = ephemeris
        self._reference = reference

    async def list_all(self, filter: CatalogFilter) -> list[CatalogObject]:
        if not self._reference.ready:
            return []
        if filter.kind is not None:
            if filter.kind in self._fixed.KINDS:
                return await self._fixed.list_objects(filter)
            if filter.kind in self._ephemeris.KINDS:
                return await self._ephemeris.list_objects(filter)
            return []
        widened = filter.model_copy(
            update={"limit": filter.limit + filter.offset, "offset": 0}
        )
        merged: list[CatalogObject] = []
        merged.extend(await self._fixed.list_objects(widened))
        merged.extend(await self._ephemeris.list_objects(widened))
        merged.sort(
            key=lambda o: (o.mag if o.mag is not None else float("inf"), o.name)
        )
        return merged[filter.offset : filter.offset + filter.limit]

    async def get_by_qualified_id(self, obj_id: str) -> CatalogObject | None:
        if not self._reference.ready:
            return None
        obj = await self._fixed.get_object(obj_id)
        if obj is not None:
            return obj
        return await self._ephemeris.get_object(obj_id)
