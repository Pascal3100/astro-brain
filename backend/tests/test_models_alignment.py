"""Tests Pydantic for alignment models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)


def test_star_validates_magnitude_and_coords() -> None:
    s = Star(id="vega", name="Vega", bayer="α Lyrae", ra_deg=279.234, dec_deg=38.784, mag=0.03)
    assert s.id == "vega"
    assert s.mag == pytest.approx(0.03)


def test_star_rejects_out_of_range_ra() -> None:
    with pytest.raises(ValidationError):
        Star(id="x", name="X", bayer="-", ra_deg=400.0, dec_deg=0.0, mag=1.0)


def test_star_record_holds_sky_and_mount_pairs() -> None:
    r = StarRecord(
        star_id="vega", sky_az=248.1, sky_alt=42.0, mount_az=247.9, mount_alt=41.7,
    )
    assert r.mount_az == pytest.approx(247.9)


def test_alignment_session_starts_empty() -> None:
    sess = AlignmentSession(
        session_id="s1",
        candidates=[],
        recorded_stars=[],
        current_idx=0,
    )
    assert sess.recorded_count == 0


def test_alignment_model_roundtrip_dict() -> None:
    m = AlignmentModel(
        recorded_stars=[],
        svd_matrix=[[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]],
        rms_arcmin=4.2,
        residuals={"vega": 4.2},
        validated_at_utc="2026-05-09T22:47:00Z",
        gps_lat=48.8566,
        gps_lon=2.3522,
        quality="good",
    )
    assert m.model_dump()["rms_arcmin"] == pytest.approx(4.2)
