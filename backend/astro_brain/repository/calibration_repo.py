"""Typed CRUD on the ``calibration_sensor`` table."""

from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite

from astro_brain.models.calibration import (
    Adxl345Offsets,
    CalibrationStatus,
    Lis3mdlOffsets,
)

SENSOR_IDS = frozenset({"lis3mdl", "adxl345_mount", "adxl345_tube"})

_ADXL_SENSORS = frozenset({"adxl345_mount", "adxl345_tube"})


def _check_sensor_id(sensor_id: str) -> None:
    if sensor_id not in SENSOR_IDS:
        raise ValueError(f"unknown sensor_id: {sensor_id!r}")


def _check_payload_type(
    sensor_id: str, payload: Adxl345Offsets | Lis3mdlOffsets
) -> None:
    if sensor_id == "lis3mdl" and not isinstance(payload, Lis3mdlOffsets):
        raise TypeError(
            f"sensor_id 'lis3mdl' requires Lis3mdlOffsets, got {type(payload).__name__}"
        )
    if sensor_id in _ADXL_SENSORS and not isinstance(payload, Adxl345Offsets):
        raise TypeError(
            f"sensor_id {sensor_id!r} requires Adxl345Offsets, got {type(payload).__name__}"
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
    payload: Adxl345Offsets | Lis3mdlOffsets
    if sensor_id == "lis3mdl":
        payload = Lis3mdlOffsets.model_validate_json(payload_json)
    else:
        payload = Adxl345Offsets.model_validate_json(payload_json)

    return CalibrationStatus(
        sensor_id=sensor_id,
        calibrated_at=datetime.fromisoformat(calibrated_at_iso),
        payload=payload,
    )


async def upsert_offsets(
    db: aiosqlite.Connection,
    sensor_id: str,
    payload: Adxl345Offsets | Lis3mdlOffsets,
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
