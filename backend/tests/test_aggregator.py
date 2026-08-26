"""Tests for the ``compute_overall`` aggregator."""

from __future__ import annotations

from astro_brain.aggregator import compute_overall
from astro_brain.subsystems import SubsystemState


def _ss(state: str) -> SubsystemState:
    return SubsystemState(state=state)


def test_all_ready_is_green() -> None:
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "tracking": _ss("sidereal"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "green"


def test_mount_disconnected_is_red() -> None:
    result = compute_overall(
        {
            "mount": _ss("disconnected"),
            "tracking": _ss("off"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "red"


def test_mount_error_is_red() -> None:
    result = compute_overall({"mount": _ss("error")})
    assert result == "red"


def test_mount_connecting_is_blue() -> None:
    result = compute_overall({"mount": _ss("connecting")})
    assert result == "blue"


def test_system_warning_is_orange() -> None:
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "system": _ss("warning"),
        }
    )
    assert result == "orange"


def test_network_offline_is_orange() -> None:
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "network": _ss("offline"),
        }
    )
    assert result == "orange"


def test_mount_moving_is_green() -> None:
    result = compute_overall(
        {
            "mount": _ss("moving"),
            "tracking": _ss("sidereal"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "green"


def test_blue_beats_orange_when_both_apply() -> None:
    result = compute_overall(
        {
            "mount": _ss("connecting"),
            "system": _ss("warning"),
        }
    )
    assert result == "blue"
