"""Tests for the ADXL345 bias+sigma helper."""

import numpy as np
import pytest

from astro_brain.services._bias_fit import compute_bias_and_sigma


def test_immobile_sensor_returns_clean_bias() -> None:
    """100 identical samples → bias == sample, sigma == 0."""
    samples = [(1.0, 0.0, 0.0)] * 100
    bias, sigma = compute_bias_and_sigma(samples)
    assert bias == pytest.approx((1.0, 0.0, 0.0))
    assert sigma == pytest.approx(0)


def test_noisy_sensor_yields_nonzero_sigma() -> None:
    """200 samples with gaussian noise std=0.02 g → sigma > 0.01, bias ≈ (0, 0, 1)."""
    rng = np.random.default_rng(42)
    noise = rng.normal(scale=0.02, size=(200, 3))
    center = np.array([0.0, 0.0, 1.0])
    samples = [(float(x), float(y), float(z)) for x, y, z in center + noise]

    bias, sigma = compute_bias_and_sigma(samples)

    assert sigma > 0.01
    assert bias == pytest.approx((0.0, 0.0, 1.0), abs=0.01)


def test_empty_samples_raises() -> None:
    """Empty input must raise ValueError with a clear message."""
    with pytest.raises(ValueError, match="samples must not be empty"):
        compute_bias_and_sigma([])
