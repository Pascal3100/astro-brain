"""Shared LIS3MDL sample generators for calibration tests.

Used by both ``test_calibration_service.py`` and ``test_calibration_routes.py``
to avoid duplicating the sphere-sampling helper.
"""

from __future__ import annotations

import numpy as np


def full_sphere_samples(n: int, seed: int = 42) -> list[tuple[float, float, float]]:
    """n points spread over the full unit sphere — good coverage."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal((n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v *= 40.0  # arbitrary non-unit radius, order of magnitude of real µT readings
    return [tuple(row) for row in v.tolist()]
