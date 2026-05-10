"""SVD-based alignment solver.

On résout `R · sky_unit = mount_unit` au sens des moindres carrés via SVD,
où `sky_unit` et `mount_unit` sont les vecteurs unitaires associés aux
coordonnées (az, alt) de chaque étoile. Le modèle est une matrice 3×3.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np

from astro_brain.models.alignment import AlignmentModel, StarRecord


def _az_alt_to_unit_vec(az_deg: float, alt_deg: float) -> np.ndarray:
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    return np.array(
        [math.cos(alt) * math.cos(az), math.cos(alt) * math.sin(az), math.sin(alt)]
    )


def _unit_vec_to_az_alt(v: np.ndarray) -> tuple[float, float]:
    norm = float(np.linalg.norm(v))
    x, y, z = v / norm
    alt = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    az = math.degrees(math.atan2(y, x)) % 360.0
    return az, alt


def compute_alignment(
    records: list[StarRecord],
    *,
    quality_threshold_arcmin: float = 20.0,
) -> AlignmentModel:
    """Calcule la matrice 3×3 de transformation et les résiduels.

    Renvoie un `AlignmentModel` non persisté (pas de gps/timestamp).
    """
    if len(records) < 3:
        raise ValueError("au moins 3 records requis")

    sky = np.column_stack(
        [_az_alt_to_unit_vec(r.sky_az, r.sky_alt) for r in records]
    )  # 3×N
    mount = np.column_stack(
        [_az_alt_to_unit_vec(r.mount_az, r.mount_alt) for r in records]
    )  # 3×N

    # Recherche R minimisant ||R·sky - mount||²
    h = sky @ mount.T
    u, _, vt = np.linalg.svd(h)
    d = np.linalg.det(vt.T @ u.T)
    s_diag = np.diag([1.0, 1.0, d])
    rotation = vt.T @ s_diag @ u.T

    residuals: dict[str, float] = {}
    sq_sum = 0.0
    for r in records:
        sky_v = _az_alt_to_unit_vec(r.sky_az, r.sky_alt)
        predicted = rotation @ sky_v
        actual = _az_alt_to_unit_vec(r.mount_az, r.mount_alt)
        cos_angle = float(np.clip(np.dot(predicted, actual), -1.0, 1.0))
        angle_deg = math.degrees(math.acos(cos_angle))
        angle_arcmin = angle_deg * 60.0
        residuals[r.star_id] = angle_arcmin
        sq_sum += angle_arcmin ** 2

    rms = math.sqrt(sq_sum / len(records))
    quality = "good" if rms < quality_threshold_arcmin else "poor"

    return AlignmentModel(
        recorded_stars=list(records),
        svd_matrix=rotation.tolist(),
        rms_arcmin=rms,
        residuals=residuals,
        validated_at_utc=datetime.now(UTC),
        gps_lat=None,
        gps_lon=None,
        quality=quality,
    )
