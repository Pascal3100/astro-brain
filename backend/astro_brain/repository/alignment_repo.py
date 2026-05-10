"""Persistance du modèle d'alignement avec garde-fous Δt 12h / ΔGPS 20m."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import aiosqlite

from astro_brain.models.alignment import AlignmentModel, StarRecord

MAX_AGE = timedelta(hours=12)
MAX_GPS_DELTA_M = 20.0
EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = (math.radians(a[0]), math.radians(a[1]))
    lat2, lon2 = (math.radians(b[0]), math.radians(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


async def save(db: aiosqlite.Connection, model: AlignmentModel) -> None:
    """Insert or replace l'unique row id=1."""
    await db.execute(
        "INSERT OR REPLACE INTO alignment_model "
        "(id, recorded_stars, svd_matrix, rms_arcmin, residuals, validated_at, "
        " gps_lat, gps_lon, quality) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            json.dumps([r.model_dump() for r in model.recorded_stars]),
            json.dumps(model.svd_matrix),
            model.rms_arcmin,
            json.dumps(model.residuals),
            model.validated_at_utc.isoformat(),
            model.gps_lat,
            model.gps_lon,
            model.quality,
        ),
    )
    await db.commit()


async def load(
    db: aiosqlite.Connection,
    *,
    now_utc: datetime,
    current_gps: tuple[float, float] | None,
) -> AlignmentModel | None:
    """Renvoie le modèle si frais ET position inchangée, sinon None.

    None si :
    - aucune row stockée
    - Δt > 12h
    - le row n'a pas de GPS
    - current_gps est None
    - distance > 20m
    """
    cursor = await db.execute("SELECT * FROM alignment_model WHERE id = 1")
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    cols = [
        "id",
        "recorded_stars",
        "svd_matrix",
        "rms_arcmin",
        "residuals",
        "validated_at",
        "gps_lat",
        "gps_lon",
        "quality",
    ]
    data = dict(zip(cols, row, strict=True))

    validated_at = datetime.fromisoformat(data["validated_at"])
    if validated_at.tzinfo is None:
        validated_at = validated_at.replace(tzinfo=now_utc.tzinfo)
    if (now_utc - validated_at) > MAX_AGE:
        return None
    if data["gps_lat"] is None or data["gps_lon"] is None or current_gps is None:
        return None
    delta = _haversine_m(current_gps, (data["gps_lat"], data["gps_lon"]))
    if delta > MAX_GPS_DELTA_M:
        return None

    return AlignmentModel(
        recorded_stars=[
            StarRecord.model_validate(r) for r in json.loads(data["recorded_stars"])
        ],
        svd_matrix=json.loads(data["svd_matrix"]),
        rms_arcmin=data["rms_arcmin"],
        residuals=json.loads(data["residuals"]),
        validated_at_utc=data["validated_at"],
        gps_lat=data["gps_lat"],
        gps_lon=data["gps_lon"],
        quality=data["quality"],
    )


async def clear(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM alignment_model WHERE id = 1")
    await db.commit()
