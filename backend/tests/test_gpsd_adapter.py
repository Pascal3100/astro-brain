"""Tests for :func:`astro_brain.adapters.gpsd_adapter.mode_to_state`.

Only the pure mode-classification function is exercised — the gpsd loop
itself is covered by manual smoke on the Pi (see the deployment
checklist in Task 17).
"""

from __future__ import annotations

from astro_brain.adapters.gpsd_adapter import mode_to_state


def test_mode_to_state_fix_2d() -> None:
    assert mode_to_state(mode=2, satellites=5) == "fix_2d"


def test_mode_to_state_fix_3d() -> None:
    assert mode_to_state(mode=3, satellites=8) == "fix_3d"


def test_mode_to_state_searching_when_sats_without_fix() -> None:
    # antenna sees satellites but not enough for a fix yet
    assert mode_to_state(mode=1, satellites=3) == "searching"


def test_mode_to_state_no_fix_when_mode_unknown_and_no_sats() -> None:
    assert mode_to_state(mode=0, satellites=0) == "no_fix"


def test_mode_to_state_no_fix_when_mode_1_and_no_sats() -> None:
    assert mode_to_state(mode=1, satellites=0) == "no_fix"
