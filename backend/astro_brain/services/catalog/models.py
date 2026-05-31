"""Pydantic models for the unified catalogue."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CatalogKind = Literal["star", "messier", "planet", "comet"]


class CatalogObject(BaseModel):
    """One celestial object served by the catalogue layer."""

    qualified_id: str
    kind: CatalogKind
    name: str
    designation: str | None = None
    ra_deg: float
    dec_deg: float
    mag: float | None = None
    constellation: str | None = None
    object_type: str | None = None
    angular_size_arcmin: float | None = None
    altitude_deg: float | None = None
    azimuth_deg: float | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class CatalogFilter(BaseModel):
    """Server-side filters for `GET /catalog/objects`."""

    kind: str | None = None
    search: str | None = None
    max_mag: float | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
