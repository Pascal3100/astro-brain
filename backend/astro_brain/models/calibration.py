"""Pydantic payload models for sensor calibrations (LIS3MDL)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Lis3mdlOffsets(BaseModel):
    offsets: tuple[float, float, float]
    scale_matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    coverage_pct: float
    residual: float


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
    payload: Lis3mdlOffsets | None
