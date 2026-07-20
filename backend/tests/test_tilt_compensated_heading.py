"""Tests for the naive heading helper."""

import pytest

from astro_brain.services._tilt_compensated_heading import naive_heading

# ---------------------------------------------------------------------------
# naive_heading
# ---------------------------------------------------------------------------


def test_naive_heading_north_is_zero() -> None:
    """Mag pointing +x (north) → 0°."""
    assert naive_heading((1.0, 0.0, 0.0)) == pytest.approx(0.0, abs=1e-9)


def test_naive_heading_east_is_90() -> None:
    """Mag pointing +y (east) → 90°."""
    assert naive_heading((0.0, 1.0, 0.0)) == pytest.approx(90.0, abs=1e-9)


def test_naive_heading_west_is_270() -> None:
    """Mag pointing -y (west) → 270°."""
    assert naive_heading((0.0, -1.0, 0.0)) == pytest.approx(270.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Normalisation — heading always returned in [0, 360)
# ---------------------------------------------------------------------------


def test_heading_normalized_to_0_360_range() -> None:
    """All returned headings must lie in [0, 360) and never be negative."""
    test_cases = [
        (-1.0, 0.0, 0.0),   # south  → 180°
        (0.0, -1.0, 0.0),   # west   → 270°
        (-1.0, -1.0, 0.0),  # SW     → 225°
    ]
    expected_headings = [180.0, 270.0, 225.0]

    for mag, expected in zip(test_cases, expected_headings, strict=True):
        h_naive = naive_heading(mag)

        assert 0.0 <= h_naive < 360.0, f"naive out of range: {h_naive}"
        assert h_naive >= 0.0
        assert h_naive == pytest.approx(expected, abs=0.1), f"naive {mag} → {h_naive:.2f}"
