"""Tests for subsystem state enums, SubsystemState and SystemState."""

from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.subsystems import (
    MountState,
    NetworkState,
    SubsystemState,
    SystemInfoState,
    TrackingState,
)
from astro_brain.system_state import SystemState


def test_mount_states_exist() -> None:
    assert MountState.DISCONNECTED.value == "disconnected"
    assert MountState.CONNECTING.value == "connecting"
    assert MountState.READY.value == "ready"
    assert MountState.MOVING.value == "moving"
    assert MountState.ERROR.value == "error"


def test_tracking_states_exist() -> None:
    assert {s.value for s in TrackingState} == {"off", "sidereal"}


def test_network_states_exist() -> None:
    assert {s.value for s in NetworkState} == {"offline", "client", "hotspot"}


def test_system_info_states_exist() -> None:
    assert {s.value for s in SystemInfoState} == {"ok", "warning", "critical"}


def test_subsystem_state_roundtrip() -> None:
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=UTC)
    s = SubsystemState(
        state="ready",
        details={"firmware_version": "11.01"},
        since=now,
        message=None,
    )
    assert s.state == "ready"
    assert s.details == {"firmware_version": "11.01"}
    assert s.since == now
    assert s.message is None


def test_subsystem_state_serializable_to_dict() -> None:
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=UTC)
    s = SubsystemState(state="fix_3d", details={"satellites": 8}, since=now)
    d = s.to_dict()
    assert d["state"] == "fix_3d"
    assert d["details"] == {"satellites": 8}
    assert d["since"] == "2026-04-17T20:30:00+00:00"
    assert d["message"] is None


def test_system_state_holds_four_subsystems_and_overall() -> None:
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=UTC)
    state = SystemState(
        overall="green",
        subsystems={
            "mount": SubsystemState(state="ready", since=now),
            "tracking": SubsystemState(state="off", since=now),
            "network": SubsystemState(state="client", since=now),
            "system": SubsystemState(state="ok", since=now),
        },
        seq=1,
        ts=now,
    )
    assert state.overall == "green"
    assert set(state.subsystems) == {"mount", "tracking", "network", "system"}


def test_system_state_to_dict_includes_all_fields() -> None:
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=UTC)
    state = SystemState(
        overall="green",
        subsystems={"mount": SubsystemState(state="ready", since=now)},
        seq=42,
        ts=now,
    )
    d = state.to_dict()
    assert d["overall"] == "green"
    assert d["seq"] == 42
    assert d["ts"] == "2026-04-17T20:30:00+00:00"
    assert d["subsystems"]["mount"]["state"] == "ready"
