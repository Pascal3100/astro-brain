"""Pydantic payload models for sensor calibrations (ADXL345, LIS3MDL, alt limits)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class Adxl345Offsets(BaseModel):
    bias: tuple[float, float, float]
    sigma: float
    zero_alt_deg: float | None = None


class Lis3mdlOffsets(BaseModel):
    offsets: tuple[float, float, float]
    scale_matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    coverage_pct: float
    residual: float


class AltLimits(BaseModel):
    min_deg: float
    max_deg: float

    @model_validator(mode="after")
    def _check_range(self) -> "AltLimits":
        # Ordered bounds and minimum 30° usable range.
        if self.min_deg >= self.max_deg:
            raise ValueError("min_deg must be strictly less than max_deg")
        if (self.max_deg - self.min_deg) < 30:
            raise ValueError("AltLimits range must be at least 30 degrees wide")
        return self


class CalibrationProgress(BaseModel):
    state: Literal["idle", "sampling", "computing", "done", "aborted", "error"]
    samples_n: int
    coverage_pct: float
    sigma: float
    hint: str | None
    residual: float | None = None


class CalibrationStatus(BaseModel):
    sensor_id: str
    calibrated_at: datetime | None
    payload: Adxl345Offsets | Lis3mdlOffsets | None
