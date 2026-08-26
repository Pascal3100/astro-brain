"""Typed CRUD sur la table `observing_site` (singleton id=1).

Le site d'observation est la **seule** source de position du backend depuis
le retrait du module DroTek (cf. ADR 2026-08-26). Il n'est écrit que sur
action explicite de l'utilisateur — jamais automatiquement au lancement de
l'app : la garde ΔGPS 20 m de :func:`alignment_repo.load` comparerait alors
le modèle persisté à un GPS téléphone qui gigue d'une dizaine de mètres, et
invaliderait un alignement encore valide.
"""

from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite
from pydantic import BaseModel, Field


class ObservingSite(BaseModel):
    """Position d'observation persistée, avec sa date de réglage."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    set_at: datetime


async def get_site(db: aiosqlite.Connection) -> ObservingSite | None:
    """Renvoie le site persisté, ou ``None`` si aucun n'a jamais été réglé."""
    cursor = await db.execute("SELECT lat, lon, set_at FROM observing_site WHERE id = 1")
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    lat, lon, set_at_iso = row
    return ObservingSite(lat=lat, lon=lon, set_at=datetime.fromisoformat(set_at_iso))


async def set_site(db: aiosqlite.Connection, lat: float, lon: float) -> ObservingSite:
    """Écrit (ou remplace) le site et renvoie la valeur persistée.

    Valide les bornes avant d'écrire : une latitude hors [-90, 90] lève
    ``ValidationError`` plutôt que d'atterrir en base.
    """
    set_at = datetime.now(UTC)
    site = ObservingSite(lat=lat, lon=lon, set_at=set_at)

    await db.execute(
        "INSERT INTO observing_site (id, lat, lon, set_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "lat = excluded.lat, lon = excluded.lon, set_at = excluded.set_at",
        (site.lat, site.lon, set_at.isoformat()),
    )
    await db.commit()
    return site
