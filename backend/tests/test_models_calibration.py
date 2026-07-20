"""Tests for calibration Pydantic models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from astro_brain.models.calibration import (
    Adxl345Offsets,
    CalibrationProgress,
    CalibrationStatus,
    Lis3mdlOffsets,
)


def test_adxl345_offsets_round_trip_without_zero_alt() -> None:
    payload = Adxl345Offsets(bias=(0.01, -0.02, 0.03), sigma=0.005)
    json_str = payload.model_dump_json()
    parsed = Adxl345Offsets.model_validate_json(json_str)
    assert parsed == payload
    assert parsed.zero_alt_deg is None


def test_adxl345_offsets_round_trip_with_zero_alt() -> None:
    payload = Adxl345Offsets(
        bias=(0.10, 0.20, 0.30),
        sigma=0.012,
        zero_alt_deg=1.4,
    )
    json_str = payload.model_dump_json()
    parsed = Adxl345Offsets.model_validate_json(json_str)
    assert parsed == payload
    assert parsed.zero_alt_deg == 1.4


def test_lis3mdl_offsets_round_trip() -> None:
    payload = Lis3mdlOffsets(
        offsets=(1.5, -2.3, 0.8),
        scale_matrix=(
            (1.0, 0.01, 0.0),
            (0.01, 0.99, 0.02),
            (0.0, 0.02, 1.02),
        ),
        coverage_pct=87.5,
        residual=0.034,
    )
    json_str = payload.model_dump_json()
    parsed = Lis3mdlOffsets.model_validate_json(json_str)
    assert parsed == payload
    assert parsed.scale_matrix[2][2] == 1.02


def test_calibration_progress_round_trip_with_residual_none() -> None:
    progress = CalibrationProgress(
        state="sampling",
        samples_n=120,
        coverage_pct=42.0,
        sigma=0.008,
        hint="Bouge la monture en azimut",
        residual=None,
    )
    json_str = progress.model_dump_json()
    parsed = CalibrationProgress.model_validate_json(json_str)
    assert parsed == progress
    assert parsed.residual is None


def test_calibration_progress_round_trip_with_residual_value() -> None:
    progress = CalibrationProgress(
        state="done",
        samples_n=500,
        coverage_pct=95.0,
        sigma=0.003,
        hint=None,
        residual=0.012,
    )
    json_str = progress.model_dump_json()
    parsed = CalibrationProgress.model_validate_json(json_str)
    assert parsed == progress


def test_calibration_progress_rejects_invalid_state() -> None:
    with pytest.raises(ValidationError):
        CalibrationProgress(
            state="bogus",  # type: ignore[arg-type]
            samples_n=1,
            coverage_pct=0.0,
            sigma=0.0,
            hint=None,
        )


def test_calibration_status_round_trip_with_adxl_payload() -> None:
    status = CalibrationStatus(
        sensor_id="adxl_tube",
        calibrated_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        payload=Adxl345Offsets(bias=(0.0, 0.0, 0.0), sigma=0.001, zero_alt_deg=0.5),
    )
    json_str = status.model_dump_json()
    parsed = CalibrationStatus.model_validate_json(json_str)
    assert parsed == status
    assert isinstance(parsed.payload, Adxl345Offsets)


def test_calibration_status_round_trip_with_lis3mdl_payload() -> None:
    status = CalibrationStatus(
        sensor_id="compass",
        calibrated_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        payload=Lis3mdlOffsets(
            offsets=(0.1, 0.2, 0.3),
            scale_matrix=(
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
            coverage_pct=90.0,
            residual=0.02,
        ),
    )
    json_str = status.model_dump_json()
    parsed = CalibrationStatus.model_validate_json(json_str)
    assert parsed == status
    assert isinstance(parsed.payload, Lis3mdlOffsets)


def test_calibration_status_round_trip_with_no_payload() -> None:
    status = CalibrationStatus(
        sensor_id="adxl_base",
        calibrated_at=None,
        payload=None,
    )
    json_str = status.model_dump_json()
    parsed = CalibrationStatus.model_validate_json(json_str)
    assert parsed == status
    assert parsed.payload is None
    assert parsed.calibrated_at is None
