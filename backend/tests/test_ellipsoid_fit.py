"""Tests for the Li-Lawley ellipsoid fit (hard-iron + soft-iron calibration)."""

import numpy as np
import pytest

from astro_brain.services._ellipsoid_fit import compute_ellipsoid_offsets, coverage_pct


def _sphere_samples(
    rng: np.random.Generator,
    n: int,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale_z: float = 1.0,
) -> list[tuple[float, float, float]]:
    """Generate *n* points on a (possibly shifted/stretched) sphere."""
    v = rng.standard_normal((n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v[:, 2] *= scale_z
    cx, cy, cz = center
    v[:, 0] += cx
    v[:, 1] += cy
    v[:, 2] += cz
    return [tuple(row) for row in v.tolist()]


def test_fit_unit_sphere_centered_at_origin() -> None:
    rng = np.random.default_rng(42)
    samples = _sphere_samples(rng, 200)

    offsets, scale, residual = compute_ellipsoid_offsets(samples)

    assert offsets == pytest.approx((0.0, 0.0, 0.0), abs=1e-3)
    assert np.allclose(scale, np.eye(3), atol=1e-3)
    assert residual < 0.01


def test_fit_offset_sphere() -> None:
    rng = np.random.default_rng(42)
    center = (5.0, 3.0, -2.0)
    samples = _sphere_samples(rng, 200, center=center)

    offsets, scale, residual = compute_ellipsoid_offsets(samples)

    assert offsets == pytest.approx(center, abs=1e-2)
    assert residual < 0.01


def test_fit_ellipsoid_scaled_z() -> None:
    rng = np.random.default_rng(42)
    samples = _sphere_samples(rng, 200, scale_z=1.5)

    offsets, _scale, _residual = compute_ellipsoid_offsets(samples)
    scale = np.array(_scale)
    offset_arr = np.array(offsets)

    # Apply A @ (sample - offset) and verify corrected points sit on the unit sphere.
    corrected_norms = [
        float(np.linalg.norm(scale @ (np.array(s) - offset_arr))) for s in samples
    ]
    mean_error = float(np.mean(np.abs(np.array(corrected_norms) - 1.0)))
    assert mean_error < 0.05


def test_coverage_full_sphere_returns_high() -> None:
    rng = np.random.default_rng(42)
    v = rng.standard_normal((1000, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    samples = [tuple(row) for row in v.tolist()]

    assert coverage_pct(samples) >= 95.0


def test_coverage_half_sphere_returns_around_50() -> None:
    rng = np.random.default_rng(42)
    v = rng.standard_normal((1000, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v[:, 2] = np.abs(v[:, 2])  # upper hemisphere only
    samples = [tuple(row) for row in v.tolist()]

    result = coverage_pct(samples)
    assert 40.0 <= result <= 60.0
