"""Tests pour le solver SVD."""
from __future__ import annotations

import math

import pytest

from astro_brain.models.alignment import StarRecord
from astro_brain.services._alignment_solver import compute_alignment


def _identity_records() -> list[StarRecord]:
    return [
        StarRecord(star_id="a", sky_az=0.0, sky_alt=30.0, mount_az=0.0, mount_alt=30.0),
        StarRecord(star_id="b", sky_az=120.0, sky_alt=45.0, mount_az=120.0, mount_alt=45.0),
        StarRecord(star_id="c", sky_az=240.0, sky_alt=60.0, mount_az=240.0, mount_alt=60.0),
    ]


def test_perfect_input_yields_near_zero_rms() -> None:
    model = compute_alignment(_identity_records())
    assert model.rms_arcmin < 1e-3
    for v in model.residuals.values():
        assert v < 1e-3


def test_constant_offset_rms_near_zero() -> None:
    """Offset constant (2° en az) → rotation pure, RMS proche de 0."""
    records = [
        StarRecord(star_id="a", sky_az=0.0, sky_alt=30.0, mount_az=2.0, mount_alt=30.0),
        StarRecord(star_id="b", sky_az=120.0, sky_alt=45.0, mount_az=122.0, mount_alt=45.0),
        StarRecord(star_id="c", sky_az=240.0, sky_alt=60.0, mount_az=242.0, mount_alt=60.0),
    ]
    model = compute_alignment(records)
    assert model.rms_arcmin < 5  # tolérance arc-min


def test_outlier_residual_isolates_bad_star() -> None:
    """1 étoile mal centrée (résiduel artificiel 30') → identifiée comme outlier."""
    records = _identity_records()
    # Décale brutalement b en alt
    records[1] = records[1].model_copy(update={"mount_alt": records[1].mount_alt + 0.5})
    model = compute_alignment(records)
    by_resid = sorted(model.residuals.items(), key=lambda kv: kv[1])
    outlier_id, outlier_val = by_resid[-1]
    others = [v for _, v in by_resid[:-1]]
    assert outlier_id == "b"
    # Avec 3 points et Kabsch SVD le ratio est borné géométriquement (~1.6 max).
    # 1.5× suffit pour identifier le badly-centred star. Le seuil UI 3× pour
    # afficher "outlier highlighted" est un heuristique séparé (cf. T17).
    assert outlier_val > 1.5 * (sum(others) / len(others))


def test_residuals_unit_arcmin() -> None:
    """Sanity : si les résiduels sont en degrés, on aurait < 1. En arc-min on a > 1
    pour un offset 0.5°."""
    records = _identity_records()
    records[1] = records[1].model_copy(update={"mount_alt": records[1].mount_alt + 0.5})
    model = compute_alignment(records)
    assert max(model.residuals.values()) > 1.0


def test_rejects_less_than_3_records() -> None:
    with pytest.raises(ValueError):
        compute_alignment(_identity_records()[:2])
