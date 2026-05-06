"""Tests for the tilt-compensated heading helper."""

import math

import numpy as np
import pytest

from astro_brain.services._tilt_compensated_heading import (
    naive_heading,
    tilt_compensated_heading,
)

B = 50.0  # realistic magnetic field strength in µT


def _rx(phi: float) -> np.ndarray:
    """Right-hand rotation matrix about +x by ``phi`` radians."""
    c, s = math.cos(phi), math.sin(phi)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _ry(theta: float) -> np.ndarray:
    """Right-hand rotation matrix about +y by ``theta`` radians."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rz(psi: float) -> np.ndarray:
    """Right-hand rotation matrix about +z by ``psi`` radians."""
    c, s = math.cos(psi), math.sin(psi)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


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
# tilt_compensated_heading — zero tilt matches naive
# ---------------------------------------------------------------------------


def test_tilt_comp_zero_tilt_matches_naive() -> None:
    """Accel (0, 0, 1) — gravity straight down, level platform.

    All four cardinal mag vectors must match naive_heading within 0.1°.
    """
    accel_level = (0.0, 0.0, 1.0)
    cardinals = [
        (1.0, 0.0, 0.0),   # north  → 0°
        (0.0, 1.0, 0.0),   # east   → 90°
        (-1.0, 0.0, 0.0),  # south  → 180°
        (0.0, -1.0, 0.0),  # west   → 270°
    ]
    for mag in cardinals:
        expected = naive_heading(mag)
        result = tilt_compensated_heading(mag, accel_level)
        assert result == pytest.approx(expected, abs=0.1), (
            f"mag={mag}: tilt_comp={result:.4f} vs naive={expected:.4f}"
        )


# ---------------------------------------------------------------------------
# tilt_compensated_heading — pitch recovery
# ---------------------------------------------------------------------------


def test_tilt_comp_5deg_pitch_recovers_heading() -> None:
    """5° nose-up pitch: tilt_compensated_heading recovers 0°; naive deviates.

    Rotation about +y (pitch up by 5°):
      mx' = mx*cos(5°) + mz*sin(5°)   — mz was 0 so m_pitched = (B*cos5°, 0, -B*sin5°)
    Wait — the spec docstring has +z down, and a nose-up pitch means
    the sensor +x axis rotates upward (away from ground).  In that frame
    a 5° nose-up pitch brings +x upward, so the horizontal component B
    projects as:
      m_pitched_x = B * cos(5°)
      m_pitched_z = -B * sin(5°)   (+z is down; tilting nose up means z-component < 0)
    Accel under nose-up pitch: gravity vector shifts toward -x in sensor frame:
      accel = (-sin(5°), 0, cos(5°))
    """
    angle = math.radians(5.0)
    m_pitched = (B * math.cos(angle), 0.0, -B * math.sin(angle))
    accel_pitched = (-math.sin(angle), 0.0, math.cos(angle))

    result = tilt_compensated_heading(m_pitched, accel_pitched)
    assert result == pytest.approx(0.0, abs=0.1)


# ---------------------------------------------------------------------------
# tilt_compensated_heading — roll recovery
# ---------------------------------------------------------------------------


def test_tilt_comp_10deg_roll_recovers_heading() -> None:
    """10° roll: mag pointing east, tilt_compensated_heading recovers 90°.

    Roll about +x by +10°: the y-axis tilts down, z-axis tilts toward -y.
    Magnetic east vector (0, B, 0) transforms to:
      m_rolled = (0, B*cos(10°), -B*sin(10°))
    Accel under +10° roll (right side dips):
      accel = (0, sin(10°), cos(10°))
    """
    angle = math.radians(10.0)
    m_rolled = (0.0, B * math.cos(angle), -B * math.sin(angle))
    accel_rolled = (0.0, math.sin(angle), math.cos(angle))

    result = tilt_compensated_heading(m_rolled, accel_rolled)
    assert result == pytest.approx(90.0, abs=0.1)


# ---------------------------------------------------------------------------
# tilt_compensated_heading — combined yaw + pitch + roll (régression I1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pitch_deg, roll_deg, heading_deg",
    [
        (5.0, 10.0, 0.0),
        (5.0, 10.0, 45.0),
        (5.0, 10.0, 90.0),
        (5.0, 10.0, 180.0),
        (-15.0, 20.0, 270.0),
        (10.0, -25.0, 135.0),
        (0.0, 30.0, 60.0),
        (30.0, 0.0, 200.0),
    ],
)
def test_tilt_comp_combined_pitch_roll_recovers_heading(
    pitch_deg: float, roll_deg: float, heading_deg: float
) -> None:
    """Combined pitch + roll : heading recovered within 0.1°.

    Convention : on définit le « heading » h comme l'angle polaire du
    champ magnétique dans le repère body level (m_level = (B cos h, B sin h, 0),
    cohérent avec ``naive_heading``). Le repère body courant est obtenu en
    appliquant R = R_y(pitch) @ R_x(roll) au repère level, donc
    m_body = R^T @ m_level et a_body = R^T @ (0, 0, 1).

    Test de non-régression pour I1 : la formule pré-fix mélangeait les
    termes croisés et introduisait une erreur ~0.87° sur (5°, 10°, 0°).
    """
    pitch = math.radians(pitch_deg)
    roll = math.radians(roll_deg)
    heading_rad = math.radians(heading_deg)

    rotation = _ry(pitch) @ _rx(roll)
    m_level = np.array(
        [B * math.cos(heading_rad), B * math.sin(heading_rad), 0.0]
    )
    g_level = np.array([0.0, 0.0, 1.0])

    m_body = rotation.T @ m_level
    a_body = rotation.T @ g_level

    result = tilt_compensated_heading(
        (float(m_body[0]), float(m_body[1]), float(m_body[2])),
        (float(a_body[0]), float(a_body[1]), float(a_body[2])),
    )
    assert result == pytest.approx(heading_deg, abs=0.1)


# ---------------------------------------------------------------------------
# Normalisation — both functions always return [0, 360)
# ---------------------------------------------------------------------------


def test_heading_normalized_to_0_360_range() -> None:
    """All returned headings must lie in [0, 360) and never be negative."""
    accel_level = (0.0, 0.0, 1.0)
    test_cases = [
        (-1.0, 0.0, 0.0),   # south  → 180°
        (0.0, -1.0, 0.0),   # west   → 270°
        (-1.0, -1.0, 0.0),  # SW     → 225°
    ]
    expected_headings = [180.0, 270.0, 225.0]

    for mag, expected in zip(test_cases, expected_headings, strict=True):
        h_naive = naive_heading(mag)
        h_tilt = tilt_compensated_heading(mag, accel_level)

        assert 0.0 <= h_naive < 360.0, f"naive out of range: {h_naive}"
        assert 0.0 <= h_tilt < 360.0, f"tilt_comp out of range: {h_tilt}"
        assert h_naive >= 0.0
        assert h_tilt >= 0.0
        assert h_naive == pytest.approx(expected, abs=0.1), f"naive {mag} → {h_naive:.2f}"
        assert h_tilt == pytest.approx(expected, abs=0.1), f"tilt {mag} → {h_tilt:.2f}"
