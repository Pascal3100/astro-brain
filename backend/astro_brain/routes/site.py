"""Routes REST du site d'observation.

``GET /site`` renvoie ``null`` quand aucun site n'est réglé : l'absence est
un état nominal (première installation, site jamais renseigné), pas une
erreur — d'où un 200 plutôt qu'un 404.

``PUT /site`` persiste **et** met à jour le provider de position en mémoire,
pour que ``/align/start`` débloque immédiatement sans attendre un redémarrage.
"""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from astro_brain import deps
from astro_brain.repository import site_repo
from astro_brain.repository.site_repo import ObservingSite

router = APIRouter(tags=["site"])


class _SiteBody(BaseModel):
    """Coordonnées du site, bornes validées par Pydantic (422 si hors plage)."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


@router.get("/site")
async def get_site(
    db: aiosqlite.Connection = Depends(deps.get_db),
) -> ObservingSite | None:
    """Renvoie le site d'observation persisté, ou ``null`` s'il n'y en a pas."""
    return await site_repo.get_site(db)


@router.put("/site", status_code=status.HTTP_204_NO_CONTENT)
async def put_site(
    body: _SiteBody,
    db: aiosqlite.Connection = Depends(deps.get_db),
    position: Any = Depends(deps.get_position_provider),
) -> Response:
    """Règle le site d'observation (persisté + appliqué à chaud)."""
    site = await site_repo.set_site(db, body.lat, body.lon)
    position.set_site(site.lat, site.lon)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
