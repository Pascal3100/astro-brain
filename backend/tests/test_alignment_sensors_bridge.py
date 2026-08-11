"""Unit tests for the GpsSource → AlignmentServiceImpl sensors adapter."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.app import _AlignmentSensorsBridge
from astro_brain.services.interfaces import GpsFix


def _now() -> datetime:
    return datetime.now(UTC)


class _StubGps:
    """Minimal :class:`GpsSource` stub — injects a fixed fix (or None)."""

    def __init__(self, fix: GpsFix | None = None) -> None:
        self._fix = fix

    def latest_fix(self) -> GpsFix | None:
        return self._fix


def test_gps_fix_returns_none_when_no_fix() -> None:
    bridge = _AlignmentSensorsBridge(_StubGps(None))
    assert bridge.gps_fix() is None


def test_gps_fix_returns_none_when_fix_is_2d() -> None:
    fix = GpsFix(lat=48.0, lon=2.0, timestamp=_now(), is_3d=False)
    bridge = _AlignmentSensorsBridge(_StubGps(fix))
    assert bridge.gps_fix() is None


def test_gps_fix_returns_tuple_when_fix_3d() -> None:
    fix = GpsFix(lat=48.5, lon=2.3, timestamp=_now(), is_3d=True)
    bridge = _AlignmentSensorsBridge(_StubGps(fix))
    assert bridge.gps_fix() == (48.5, 2.3)


def test_observer_returns_none_without_fix_or_client() -> None:
    bridge = _AlignmentSensorsBridge(_StubGps(None))
    assert bridge.observer() is None


def test_observer_uses_client_location_when_no_fix() -> None:
    bridge = _AlignmentSensorsBridge(_StubGps(None))
    bridge.set_client_location(43.6, 1.44)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (43.6, 1.44)


def test_pi_fix_takes_precedence_over_client() -> None:
    fix = GpsFix(lat=48.0, lon=2.0, timestamp=_now(), is_3d=True)
    bridge = _AlignmentSensorsBridge(_StubGps(fix))
    bridge.set_client_location(0.0, 0.0)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (48.0, 2.0)


def test_observer_uses_gps_when_available() -> None:
    fix = GpsFix(lat=10.0, lon=20.0, timestamp=_now(), is_3d=True)
    bridge = _AlignmentSensorsBridge(_StubGps(fix))
    obs = bridge.observer()
    assert obs is not None
    assert obs.lat_deg == 10.0
    assert obs.lon_deg == 20.0
