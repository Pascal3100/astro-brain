"""Routes REST du wizard d'alignement.

Erreurs :
- ConflictError → 409
- SensorUnavailableError → 503
- ValueError du solver → 422
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
from astro_brain.repository import site_repo
from astro_brain.services._alignment_catalog import MountLimits, visible_stars
from astro_brain.services.constellation_figures import figure_for, render_figure
from astro_brain.services.interfaces import (
    AlignmentService,
    ConflictError,
    SensorUnavailableError,
)
from astro_brain.subsystems import SubsystemState


def _publish_session(bus: StateBus, service: AlignmentService) -> None:
    """Publish the current alignment session state to the bus.

    Called after every mutating route so the SSE stream reflects the wizard
    state in real time. Idempotent (safe to call when nothing changed).
    """
    sess = service.session()
    if sess is None:
        bus.publish(
            "alignment",
            SubsystemState(
                state="idle",
                details={"is_aligned": service.is_aligned},
                since=datetime.now(UTC),
            ),
        )
        return
    bus.publish(
        "alignment",
        SubsystemState(
            state="active",
            details={
                "is_aligned": service.is_aligned,
                "session_id": sess.session_id,
                "current_idx": sess.current_idx,
                "recorded_count": len(sess.recorded_stars),
                "candidate_ids": [c.id for c in sess.candidates],
            },
            since=datetime.now(UTC),
        ),
    )


router = APIRouter(tags=["alignment"], prefix="/align")


class _ClientLocationBody(BaseModel):
    lat: float
    lon: float


class _RecordBody(BaseModel):
    idx: int


class _SwapBody(BaseModel):
    star: Star


class _RestartBody(BaseModel):
    idx: int


@router.get("/session")
async def get_session(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> dict[str, AlignmentSession | None]:
    return {"session": service.session()}


@router.post("/location/client")
async def set_client_location(
    body: _ClientLocationBody,
    db: aiosqlite.Connection = Depends(deps.get_db),
    position: Any = Depends(deps.get_position_provider),
) -> dict[str, bool]:
    """Règle le site d'observation depuis le GPS du téléphone.

    Appelée par l'app quand ``/align/start`` renvoie 409 faute de position.
    Alias historique de ``PUT /site`` : elle **persiste** désormais, au lieu
    de ne vivre qu'en RAM jusqu'au prochain redémarrage. Elle disparaîtra
    quand l'app aura basculé sur ``PUT /site``.
    """
    site = await site_repo.set_site(db, body.lat, body.lon)
    position.set_site(site.lat, site.lon)
    return {"ok": True}


@router.post("/start")
async def start(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
    position: Any = Depends(deps.get_position_provider),
) -> AlignmentSession:
    if position.position() is None:
        raise HTTPException(status_code=409, detail="position requise")
    try:
        sess = await service.start()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/swap/{idx}")
async def swap(
    idx: int,
    body: _SwapBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.swap(idx, body.star)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/record")
async def record(
    body: _RecordBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.record(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except SensorUnavailableError as e:
        # Encodeurs monture illisibles : refus lisible plutôt qu'un 500.
        raise HTTPException(status_code=503, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/restart_star")
async def restart_star(
    body: _RestartBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentSession:
    try:
        sess = await service.restart_star(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess


@router.post("/finalize")
async def finalize(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> AlignmentModel:
    try:
        model = await service.finalize()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _publish_session(bus, service)
    return model


@router.delete("/session", status_code=204)
async def cancel(
    service: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> Response:
    await service.cancel()
    _publish_session(bus, service)
    return Response(status_code=204)


@router.get("/constellation/{abbr}")
async def get_constellation(
    abbr: str,
    target_ra: float,
    target_dec: float,
    position: Any = Depends(deps.get_position_provider),
) -> dict[str, Any]:
    """Renvoie la figure de la constellation et marque l'étoile cible.

    - 404 si l'abréviation n'est pas dans l'asset des figures.
    - ``oriented`` = True si une position est disponible (az/alt calculés).
    """
    figure = figure_for(abbr)
    if figure is None:
        raise HTTPException(status_code=404, detail=f"constellation inconnue: {abbr}")
    obs = position.observer()
    t = datetime.now(UTC) if obs is not None else None
    rendered = render_figure(
        figure,
        target_ra=target_ra,
        target_dec=target_dec,
        observer=obs,
        t_utc=t,
    )
    return {"abbr": abbr, **rendered}


@router.get("/stars/visible")
async def get_visible_stars(
    position: Any = Depends(deps.get_position_provider),
) -> dict[str, Any]:
    """Étoiles d'alignement actuellement pointables, groupées par constellation.

    Requiert un site d'observation réglé — 409 sinon.
    """
    obs = position.observer()
    if obs is None:
        raise HTTPException(status_code=409, detail="position requise")
    # Bornes pleine-voûte (mêmes valeurs que select_candidates) ; le Setup tube
    # affinera plus tard. alt_min=10.0 ici est nominal : le plancher
    # effectivement appliqué est 20° (défaut `min_alt` de `visible_stars`,
    # qui prime sur `limits.alt_min` dans le filtre).
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    groups = visible_stars(obs, datetime.now(UTC), limits)
    return {
        "constellations": {
            abbr: [
                {
                    "id": s.id,
                    "name": s.name,
                    "bayer": s.bayer,
                    "ra_deg": s.ra_deg,
                    "dec_deg": s.dec_deg,
                    "mag": s.mag,
                    "az": round(az, 2),
                    "alt": round(alt, 2),
                }
                for s, az, alt in entries
            ]
            for abbr, entries in groups.items()
        }
    }
