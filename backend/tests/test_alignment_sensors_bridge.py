"""Unit tests for the observing-site → AlignmentServiceImpl sensors adapter."""
from __future__ import annotations

from astro_brain.app import _AlignmentSensorsBridge


def test_position_is_none_when_site_never_set() -> None:
    assert _AlignmentSensorsBridge().position() is None


def test_position_returns_site_once_set() -> None:
    bridge = _AlignmentSensorsBridge()
    bridge.set_site(43.6, 1.44)
    assert bridge.position() == (43.6, 1.44)


def test_clear_site_drops_the_position() -> None:
    bridge = _AlignmentSensorsBridge()
    bridge.set_site(43.6, 1.44)
    bridge.clear_site()
    assert bridge.position() is None
    assert bridge.site() is None


def test_observer_returns_none_without_site() -> None:
    assert _AlignmentSensorsBridge().observer() is None


def test_observer_uses_the_site() -> None:
    bridge = _AlignmentSensorsBridge()
    bridge.set_site(43.6, 1.44)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (43.6, 1.44)


def test_set_site_overwrites_the_previous_one() -> None:
    bridge = _AlignmentSensorsBridge()
    bridge.set_site(43.6, 1.44)
    bridge.set_site(48.85, 2.35)
    assert bridge.position() == (48.85, 2.35)
