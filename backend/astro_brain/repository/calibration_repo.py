"""Typed CRUD on the ``calibration_sensor`` table."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import aiosqlite
from pydantic import ValidationError

from astro_brain.models.calibration import CalibrationStatus, Lis3mdlOffsets

_log = logging.getLogger(__name__)

SENSOR_IDS = frozenset({"lis3mdl"})


def _check_sensor_id(sensor_id: str) -> None:
    if sensor_id not in SENSOR_IDS:
        raise ValueError(f"unknown sensor_id: {sensor_id!r}")


def _check_payload_type(sensor_id: str, payload: Lis3mdlOffsets) -> None:
    if sensor_id == "lis3mdl" and not isinstance(payload, Lis3mdlOffsets):
        raise TypeError(
            f"sensor_id 'lis3mdl' requires Lis3mdlOffsets, got {type(payload).__name__}"
        )


async def get_offsets(db: aiosqlite.Connection, sensor_id: str) -> CalibrationStatus:
    """Return the stored calibration for ``sensor_id`` or an empty status if missing."""
    _check_sensor_id(sensor_id)

    cursor = await db.execute(
        "SELECT payload_json, calibrated_at FROM calibration_sensor WHERE sensor_id = ?",
        (sensor_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()

    if row is None:
        return CalibrationStatus(sensor_id=sensor_id, calibrated_at=None, payload=None)

    payload_json, calibrated_at_iso = row
    payload: Lis3mdlOffsets | None
    try:
        payload = Lis3mdlOffsets.model_validate_json(payload_json)
    except ValidationError as exc:
        # DB row corrompue (schema legacy, payload tronqué…) : on dégrade
        # gracefully en « non calibré » plutôt que de propager un 500.
        _log.warning(
            "calibration row for %r is invalid (%s); treating as uncalibrated",
            sensor_id,
            exc,
        )
        return CalibrationStatus(
            sensor_id=sensor_id, calibrated_at=None, payload=None
        )

    return CalibrationStatus(
        sensor_id=sensor_id,
        calibrated_at=datetime.fromisoformat(calibrated_at_iso),
        payload=payload,
    )


async def upsert_offsets(
    db: aiosqlite.Connection,
    sensor_id: str,
    payload: Lis3mdlOffsets,
) -> None:
    """Insert or replace the calibration row for ``sensor_id``."""
    _check_sensor_id(sensor_id)
    _check_payload_type(sensor_id, payload)

    payload_json = payload.model_dump_json()
    calibrated_at = datetime.now(UTC).isoformat()

    await db.execute(
        "INSERT INTO calibration_sensor (sensor_id, payload_json, calibrated_at) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(sensor_id) DO UPDATE SET "
        "payload_json = excluded.payload_json, "
        "calibrated_at = excluded.calibrated_at",
        (sensor_id, payload_json, calibrated_at),
    )
    await db.commit()
