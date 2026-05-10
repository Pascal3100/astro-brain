"""CatalogRegistry — dispatch list/get queries to the appropriate provider."""
from __future__ import annotations

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.providers import CatalogProvider


class CatalogRegistry:
    """Dispatch facade in front of one or more providers keyed by `kind`."""

    def __init__(self, providers: dict[str, CatalogProvider]) -> None:
        self._providers = providers

    async def list_all(self, filter: CatalogFilter) -> list[CatalogObject]:
        if filter.kind is not None:
            provider = self._providers.get(filter.kind)
            if provider is None:
                return []
            return await provider.list_objects(filter)

        # Sans filtre kind : interroger tous les providers, fusionner, paginer.
        # Widening: chaque provider renvoie (offset + limit) éléments depuis 0.
        # Le k-ième élément du tri global (k = offset + limit) ne peut pas être
        # plus profond que la position k dans aucune source triée individuellement,
        # donc cette fenêtre élargie suffit pour paginer correctement après merge.
        merged: list[CatalogObject] = []
        widened = filter.model_copy(
            update={"limit": filter.limit + filter.offset, "offset": 0}
        )
        for provider in self._providers.values():
            merged.extend(await provider.list_objects(widened))
        merged.sort(
            key=lambda o: (o.mag if o.mag is not None else float("inf"), o.name)
        )
        return merged[filter.offset : filter.offset + filter.limit]

    async def get_by_qualified_id(self, qid: str) -> CatalogObject | None:
        if ":" not in qid:
            return None
        kind, raw_id = qid.split(":", 1)
        provider = self._providers.get(kind)
        if provider is None:
            return None
        return await provider.get_object(raw_id)
