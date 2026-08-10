"""Routes de l'artefact de référence : statut + déclenchement de sync."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.reference.sync import ReferenceSync

router = APIRouter(tags=["reference"], prefix="/reference")


class ReferenceStatus(BaseModel):
    ready: bool
    schema_version: int | None = None
    generated_at: str | None = None
    window_start: str | None = None
    window_end: str | None = None


class SyncResponse(BaseModel):
    status: str
    schema_version: int | None = None


@router.get("/status", response_model=ReferenceStatus)
async def reference_status(
    reference: ReferenceDb = Depends(deps.get_reference_db),
) -> ReferenceStatus:
    meta = await reference.meta()
    if meta is None:
        return ReferenceStatus(ready=False)
    return ReferenceStatus(
        ready=reference.ready,
        schema_version=meta.schema_version,
        generated_at=meta.generated_at,
        window_start=meta.window_start,
        window_end=meta.window_end,
    )


@router.post("/sync", response_model=SyncResponse)
async def reference_sync(
    sync: ReferenceSync = Depends(deps.get_reference_sync),
) -> SyncResponse:
    result = await sync.sync()
    return SyncResponse(status=result.status, schema_version=result.schema_version)
