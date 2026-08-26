"""Pydantic models pour l'alignement 3 étoiles."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Star(BaseModel):
    """Étoile candidate du catalogue d'alignement."""

    id: str
    name: str
    bayer: str
    ra_deg: float = Field(ge=0, lt=360)
    dec_deg: float = Field(ge=-90, le=90)
    mag: float


class StarRecord(BaseModel):
    """Une étoile recordée pendant le wizard."""

    star_id: str
    sky_az: float
    sky_alt: float
    mount_az: float
    mount_alt: float


class AlignmentSession(BaseModel):
    """Session de wizard en cours (vit en RAM côté backend)."""

    session_id: str
    candidates: list[Star]
    recorded_stars: list[StarRecord]
    current_idx: int

    @property
    def recorded_count(self) -> int:
        return len(self.recorded_stars)


class AlignmentModel(BaseModel):
    """Modèle d'alignement finalisé, persisté en state.db."""

    recorded_stars: list[StarRecord]
    svd_matrix: list[list[float]]
    rms_arcmin: float
    residuals: dict[str, float]
    validated_at_utc: datetime
    # Noms historiques (schéma appliqué, non renommé) : depuis le retrait du
    # module DroTek (ADR 2026-08-26), la valeur est la position du **site
    # d'observation** au moment du `record`, plus un fix GPS embarqué. La
    # garde ΔGPS 20 m d'`alignment_repo.load` compare donc deux sites.
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lon: float | None = Field(default=None, ge=-180, le=180)
    quality: Literal["good", "poor"] = "good"
