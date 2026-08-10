"""Routes REST du catalogue d'objets célestes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.registry import CatalogRegistry

router = APIRouter(tags=["catalog"], prefix="/catalog")


class CatalogListResponse(BaseModel):
    objects: list[CatalogObject]
    count: int
    limit: int
    offset: int


@router.get("/objects", response_model=CatalogListResponse)
async def list_objects(
    kind: str | None = Query(default=None),
    search: str | None = Query(default=None),
    max_mag: float | None = Query(default=None),
    messier: bool = Query(default=False),
    visible_now: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    registry: CatalogRegistry = Depends(deps.get_catalog_registry),
    enricher: Any = Depends(deps.get_visibility_enricher),
) -> CatalogListResponse:
    f = CatalogFilter(
        kind=kind, search=search, max_mag=max_mag, messier_only=messier,
        limit=limit, offset=offset,
    )
    objects = await registry.list_all(f)
    objects = enricher.enrich(objects, visible_now=visible_now)
    return CatalogListResponse(
        objects=objects, count=len(objects), limit=limit, offset=offset,
    )


@router.get("/objects/{qualified_id:path}", response_model=CatalogObject)
async def get_object(
    qualified_id: str,
    registry: CatalogRegistry = Depends(deps.get_catalog_registry),
) -> Any:
    obj = await registry.get_by_qualified_id(qualified_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="object not found")
    return obj
