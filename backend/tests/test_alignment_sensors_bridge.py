"""Unit tests for the StateBus → AlignmentServiceImpl sensors adapter."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.app import _AlignmentSensorsBridge
from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState


def _publish_gps(bus: StateBus, state: str, **details: float) -> None:
    bus.publish(
        "gps",
        SubsystemState(
            state=state,
            details=dict(details),
            since=datetime.now(UTC),
        ),
    )


def test_gps_fix_returns_none_when_no_gps_subsystem() -> None:
    bridge = _AlignmentSensorsBridge(StateBus())
    assert bridge.gps_fix() is None


def test_gps_fix_returns_none_when_state_not_fix_3d() -> None:
    bus = StateBus()
    _publish_gps(bus, "fix_2d", lat=48.0, lon=2.0)
    assert _AlignmentSensorsBridge(bus).gps_fix() is None


def test_gps_fix_returns_none_when_lat_missing() -> None:
    bus = StateBus()
    _publish_gps(bus, "fix_3d", lon=2.0)
    assert _AlignmentSensorsBridge(bus).gps_fix() is None


def test_gps_fix_returns_tuple_when_fix_3d_with_lat_lon() -> None:
    bus = StateBus()
    _publish_gps(bus, "fix_3d", lat=48.5, lon=2.3)
    assert _AlignmentSensorsBridge(bus).gps_fix() == (48.5, 2.3)


def test_observer_returns_none_without_fix_or_client() -> None:
    bridge = _AlignmentSensorsBridge(StateBus())
    assert bridge.observer() is None


def test_observer_uses_client_location_when_no_fix() -> None:
    bridge = _AlignmentSensorsBridge(StateBus())
    bridge.set_client_location(43.6, 1.44)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (43.6, 1.44)


def test_pi_fix_takes_precedence_over_client() -> None:
    bus = StateBus()
    bridge = _AlignmentSensorsBridge(bus)
    bridge.set_client_location(0.0, 0.0)
    _publish_gps(bus, "fix_3d", lat=48.0, lon=2.0)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (48.0, 2.0)


def test_observer_uses_gps_when_available() -> None:
    bus = StateBus()
    _publish_gps(bus, "fix_3d", lat=10.0, lon=20.0)
    obs = _AlignmentSensorsBridge(bus).observer()
    assert obs is not None
    assert obs.lat_deg == 10.0
    assert obs.lon_deg == 20.0
