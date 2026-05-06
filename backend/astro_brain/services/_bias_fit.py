"""ADXL345 bias+sigma helper — pure numpy, zero I/O, zero state."""

import numpy as np


def compute_bias_and_sigma(
    samples: list[tuple[float, float, float]],
) -> tuple[tuple[float, float, float], float]:
    """Compute 3D mean bias + max axis sigma for an immobile-sensor dataset.

    Returns (bias, sigma) where sigma is the max stddev across axes (in g).

    Raises:
        ValueError: if *samples* is empty.
    """
    if not samples:
        raise ValueError("samples must not be empty")

    arr = np.array(samples, dtype=float)
    mx, my, mz = arr.mean(axis=0).tolist()
    sigma = float(arr.std(axis=0).max())
    return (float(mx), float(my), float(mz)), sigma
