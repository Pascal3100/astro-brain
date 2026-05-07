"""Li-Lawley algebraic ellipsoid fit for LIS3MDL magnetometer calibration.

Computes hard-iron offset (centre of the ellipsoid) and the soft-iron
correction matrix A such that A @ (sample - offset) lies on the unit sphere.

Reference: https://teslabs.com/articles/magnetometer-calibration/
Pure numpy, zero I/O, zero state.
"""

import numpy as np


def compute_ellipsoid_offsets(
    samples: list[tuple[float, float, float]],
) -> tuple[
    tuple[float, float, float],
    tuple[tuple[float, float, float], ...],
    float,
]:
    """Fit a general ellipsoid to *samples* and return calibration parameters.

    Solves the algebraic least-squares problem (Li-Lawley) for the quadric:
      a x² + b y² + c z² + 2f yz + 2g xz + 2h xy + 2p x + 2q y + 2r z = 1

    Args:
        samples: N magnetometer readings (x, y, z) in µT.

    Returns:
        offsets: Hard-iron bias vector (b_x, b_y, b_z).
        scale:   3×3 soft-iron correction matrix A as a tuple-of-tuples.
                 Apply as ``A @ (sample - offsets)`` to map onto the unit sphere.
        residual: Mean absolute deviation from the unit sphere after correction.

    Raises:
        ValueError: If *samples* is empty or the fit is degenerate.
    """
    if not samples:
        raise ValueError("samples must not be empty")

    arr = np.array(samples, dtype=float)
    x, y, z = arr[:, 0], arr[:, 1], arr[:, 2]

    # --- 1. Design matrix D (N×9) ---
    D = np.column_stack([
        x * x, y * y, z * z,
        2 * y * z, 2 * x * z, 2 * x * y,
        2 * x, 2 * y, 2 * z,
    ])

    # Least-squares: D @ v ≈ 1  →  v = (a, b, c, f, g, h, p, q, r)
    ones = np.ones(len(arr))
    v, *_ = np.linalg.lstsq(D, ones, rcond=None)

    a, b, c, f, g, h, p, q, r = v

    # --- 2. Quadric matrices ---
    M = np.array([
        [a, h, g],
        [h, b, f],
        [g, f, c],
    ])
    n = np.array([p, q, r])
    d = -1.0  # RHS was +1, so canonical form  x'Mx + 2 n'x + d = 0  has d = -1

    # Least-squares can return a sign-flipped solution (all coefficients negated)
    # when the ellipsoid centre is far from the origin.  If M is negative-definite,
    # flip the whole equation (×−1) so that M becomes positive-definite.
    if np.trace(M) < 0:
        M = -M
        n = -n
        d = -d

    # --- 3. Hard-iron offset: centre of the ellipsoid ---
    try:
        M_inv = np.linalg.inv(M)
    except np.linalg.LinAlgError as exc:
        raise ValueError("ellipsoid fit failed: degenerate samples") from exc

    b_offset = -M_inv @ n  # shape (3,)

    # --- 4. Normalisation scalar k ---
    # k = b_offset' M b_offset - d  (with d = -1)
    k = float(b_offset @ M @ b_offset - d)
    # Garde stricte : k arbitrairement petit signifie que le centre de
    # l'ellipsoïde est sur la quadric, ce qui produit M_norm explosif.
    if k < 1e-9:
        raise ValueError("ellipsoid fit failed: degenerate samples")

    # --- 5. Soft-iron correction matrix A ---
    M_norm = M / k  # centred quadric is  y' M_norm y = 1
    # Matrix square root via eigendecomposition (M_norm is symmetric)
    eigenvalues, V = np.linalg.eigh(M_norm)
    if np.any(eigenvalues <= 0):
        raise ValueError("ellipsoid fit failed: degenerate samples")

    # A = V diag(sqrt(λ)) V'  — symmetric positive-definite square root
    A = V @ np.diag(np.sqrt(eigenvalues)) @ V.T

    # --- 6. Residual on corrected samples ---
    corrected = (A @ (arr - b_offset).T).T  # shape (N, 3)
    norms = np.linalg.norm(corrected, axis=1)
    residual = float(np.mean(np.abs(norms - 1.0)))

    offsets = (float(b_offset[0]), float(b_offset[1]), float(b_offset[2]))
    scale = tuple(tuple(float(v) for v in row) for row in A.tolist())
    return offsets, scale, residual


def coverage_pct(
    samples: list[tuple[float, float, float]],
    n_quadrants: int = 4,
) -> float:
    """Discretise *samples* on the unit sphere into ``n_quadrants³`` cells.

    Returns the percentage of cells visited relative to the cells that the
    unit sphere surface can physically reach.  A full-sphere uniform
    distribution yields ~100 %; a half-sphere yields ~50 % because the
    sphere surface is split symmetrically between hemispheres.

    Args:
        samples:     Magnetometer readings; need not be normalised.
        n_quadrants: Grid resolution per axis (default 4 → 56 reachable surface
                     cells out of 4³ = 64 total).

    Returns:
        Percentage in [0.0, 100.0].
    """
    if not samples:
        return 0.0

    arr = np.array(samples, dtype=float)
    norms = np.linalg.norm(arr, axis=1)

    # Project each sample onto the unit sphere (discard zero-length vectors).
    mask = norms > 0
    if not mask.any():
        return 0.0
    unit = arr[mask] / norms[mask, np.newaxis]  # shape (M, 3)

    # Map each component from [-1, 1] → bin index in [0, n_quadrants - 1].
    bins = np.floor((unit + 1.0) / 2.0 * n_quadrants).astype(int)
    bins = np.clip(bins, 0, n_quadrants - 1)
    cells_visited = {(int(row[0]), int(row[1]), int(row[2])) for row in bins.tolist()}

    # Denominator: only cells whose bounding box intersects the unit sphere.
    # This normalises upper and lower hemispheres to ~50 % each regardless of
    # n_quadrants, because the sphere surface is symmetric about any equator.
    h = 2.0 / n_quadrants
    reachable = 0
    for i in range(n_quadrants):
        for j in range(n_quadrants):
            for k in range(n_quadrants):
                x0 = -1.0 + i * h
                y0 = -1.0 + j * h
                z0 = -1.0 + k * h
                # Squared min distance from origin to the cell box.
                cx = max(x0, min(0.0, x0 + h))
                cy = max(y0, min(0.0, y0 + h))
                cz = max(z0, min(0.0, z0 + h))
                d_min_sq = cx * cx + cy * cy + cz * cz
                # Squared max distance to the farthest corner.
                d_max_sq = (
                    max(x0 * x0, (x0 + h) * (x0 + h))
                    + max(y0 * y0, (y0 + h) * (y0 + h))
                    + max(z0 * z0, (z0 + h) * (z0 + h))
                )
                if d_min_sq <= 1.0 <= d_max_sq:
                    reachable += 1

    if reachable == 0:
        return 0.0
    return min(100.0 * len(cells_visited) / reachable, 100.0)
