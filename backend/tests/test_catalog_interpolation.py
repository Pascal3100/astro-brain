from __future__ import annotations

from datetime import UTC, datetime

import pytest

from astro_brain.services.catalog.interpolation import (
    interpolate_radec,
    lerp_angle_deg,
    parse_utc,
)


def test_parse_utc_accepts_z_suffix() -> None:
    t = parse_utc("2026-08-09T00:00:00Z")
    assert t == datetime(2026, 8, 9, 0, 0, 0, tzinfo=UTC)


def test_parse_utc_forces_utc_when_naive() -> None:
    assert parse_utc("2026-08-09T00:00:00").tzinfo == UTC


def test_lerp_angle_wraps_shortest_arc_through_zero() -> None:
    # 359° -> 1° à mi-chemin doit passer par 0°, pas par 180°
    assert lerp_angle_deg(359.0, 1.0, 0.5) == pytest.approx(0.0, abs=1e-9)


def test_interpolate_radec_midpoint() -> None:
    before = (datetime(2026, 8, 9, 0, 0, tzinfo=UTC), 100.0, 10.0)
    after = (datetime(2026, 8, 10, 0, 0, tzinfo=UTC), 102.0, 12.0)
    t = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    ra, dec = interpolate_radec(before, after, t)
    assert ra == pytest.approx(101.0)
    assert dec == pytest.approx(11.0)
