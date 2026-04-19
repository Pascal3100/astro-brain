"""Tests for programmable fake services (no hardware)."""

from __future__ import annotations

from astro_brain.bus import StateBus
from astro_brain.services.fakes import (
    FakeGps,
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
)


async def test_fake_mount_publishes_ready_on_start() -> None:
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "ready"
    assert s.details["firmware_version"] == "fake-1.0"


async def test_fake_mount_slew_transitions_to_moving() -> None:
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    await mount.slew("alt", "+", 5)
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "moving"
    assert s.details["active_slews"] == [
        {"axis": "alt", "direction": "+", "rate": 5}
    ]


async def test_fake_mount_stop_slew_returns_to_ready() -> None:
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    await mount.slew("alt", "+", 5)
    await mount.stop_slew(None)
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "ready"
    assert s.details.get("active_slews", []) == []


async def test_fake_tracking_publishes_state() -> None:
    bus = StateBus()
    tracking = FakeTracking(bus)
    await tracking.set_tracking(True)
    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"
    await tracking.set_tracking(False)
    assert bus.get_full_state().subsystems["tracking"].state == "off"


async def test_fake_gps_produces_fix_on_start() -> None:
    bus = StateBus()
    gps = FakeGps(bus, initial_state="fix_3d", lat=48.85, lon=2.35, sats=8)
    await gps.start()
    s = bus.get_full_state().subsystems["gps"]
    assert s.state == "fix_3d"
    assert s.details["lat"] == 48.85
    assert s.details["lon"] == 2.35
    assert s.details["satellites"] == 8
    await gps.stop()


async def test_fake_network_publishes_client_by_default() -> None:
    bus = StateBus()
    net = FakeNetwork(bus, state="client", ssid="Home", ip="192.168.1.10")
    await net.start()
    s = bus.get_full_state().subsystems["network"]
    assert s.state == "client"
    assert s.details["ssid"] == "Home"
    assert s.details["ip"] == "192.168.1.10"
    await net.stop()


async def test_fake_system_info_publishes_ok_within_thresholds() -> None:
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=55.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    s = bus.get_full_state().subsystems["system"]
    assert s.state == "ok"
    assert s.details["cpu_temp_c"] == 55.0
    await sys.stop()


async def test_fake_system_info_transitions_to_warning_over_threshold() -> None:
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=72.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    assert bus.get_full_state().subsystems["system"].state == "warning"
    await sys.stop()


async def test_fake_system_info_transitions_to_critical_over_threshold() -> None:
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=82.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    assert bus.get_full_state().subsystems["system"].state == "critical"
    await sys.stop()
