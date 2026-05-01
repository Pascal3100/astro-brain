"""Tests for MountIndiAdapter (start/stop, slew, tracking, watchdog)."""

from __future__ import annotations

import pytest

from astro_brain.adapters.mount_indi_adapter import (
    INDI_DEVICE_NAME,
    MountIndiAdapter,
)
from astro_brain.bus import StateBus
from tests.fakes.fake_indi import FakeIndiClient


def _seed_mount_device(client: FakeIndiClient) -> None:
    """Pre-load the fake with the properties MountIndiAdapter expects."""
    dev = client.add_device(INDI_DEVICE_NAME)
    dev.add_switch(
        "CONNECTION", {"CONNECT": "OFF", "DISCONNECT": "ON"}
    )
    dev.add_text("DEVICE_PORT", {"PORT": ""})
    dev.add_switch(
        "CONNECTION_MODE", {"CONNECTION_SERIAL": "ON", "CONNECTION_TCP": "OFF"}
    )


@pytest.mark.asyncio
async def test_start_publishes_connecting_then_ready_when_device_arrives() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    full = bus.get_full_state()
    assert full.subsystems["mount"].state == "ready"
    assert full.subsystems["tracking"].state == "off"


@pytest.mark.asyncio
async def test_start_publishes_error_when_connect_fails() -> None:
    bus = StateBus()

    class _BadClient(FakeIndiClient):
        def connectServer(self) -> bool:  # noqa: N802
            raise RuntimeError("boom")

    adapter = MountIndiAdapter(bus, client=_BadClient())
    await adapter.start()

    state = bus.get_full_state().subsystems["mount"]
    assert state.state == "error"
    assert "boom" in (state.message or "")


@pytest.mark.asyncio
async def test_stop_publishes_disconnected() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.stop()

    assert bus.get_full_state().subsystems["mount"].state == "disconnected"
    assert client.connected is False


def _seed_motion_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "TELESCOPE_MOTION_NS", {"MOTION_NORTH": "OFF", "MOTION_SOUTH": "OFF"}
    )
    dev.add_switch(
        "TELESCOPE_MOTION_WE", {"MOTION_WEST": "OFF", "MOTION_EAST": "OFF"}
    )
    dev.add_switch(
        "TELESCOPE_SLEW_RATE",
        {f"SLEW_RATE_{i}": ("ON" if i == 1 else "OFF") for i in range(1, 9)},
    )
    dev.add_switch(
        "TELESCOPE_ABORT_MOTION", {"ABORT_MOTION": "OFF"}
    )


@pytest.mark.asyncio
async def test_slew_alt_plus_rate4_pushes_slew_rate_then_motion_north() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.slew("alt", "+", 4)

    dev = client.getDevice(INDI_DEVICE_NAME)
    rate_vec = dev.getSwitch("TELESCOPE_SLEW_RATE")
    motion_ns = dev.getSwitch("TELESCOPE_MOTION_NS")
    assert rate_vec["SLEW_RATE_4"].getState() == "ON"
    assert rate_vec["SLEW_RATE_1"].getState() == "OFF"
    assert motion_ns["MOTION_NORTH"].getState() == "ON"
    assert motion_ns["MOTION_SOUTH"].getState() == "OFF"
    sent_names = [p.getName() for p in client.sent_properties]
    assert sent_names == ["TELESCOPE_SLEW_RATE", "TELESCOPE_MOTION_NS"]
    assert bus.get_full_state().subsystems["mount"].state == "moving"


@pytest.mark.asyncio
async def test_slew_az_minus_pushes_motion_east() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.slew("az", "-", 2)

    motion_we = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_MOTION_WE")
    assert motion_we["MOTION_EAST"].getState() == "ON"
    assert motion_we["MOTION_WEST"].getState() == "OFF"


@pytest.mark.asyncio
async def test_stop_slew_axis_alt_only_turns_motion_ns_off() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.slew("alt", "+", 4)

    await adapter.stop_slew("alt")

    motion_ns = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_MOTION_NS")
    assert motion_ns["MOTION_NORTH"].getState() == "OFF"
    assert motion_ns["MOTION_SOUTH"].getState() == "OFF"
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_stop_slew_no_axis_uses_abort_motion() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.slew("alt", "+", 4)
    await adapter.slew("az", "-", 4)

    await adapter.stop_slew(None)

    abort = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_ABORT_MOTION")
    assert abort["ABORT_MOTION"].getState() == "ON"
    assert bus.get_full_state().subsystems["mount"].state == "ready"


def _seed_time_location_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_text("TIME_UTC", {"UTC": "", "OFFSET": "0"})
    dev.add_number(
        "GEOGRAPHIC_COORD", {"LAT": 0.0, "LONG": 0.0, "ELEV": 0.0}
    )


@pytest.mark.asyncio
async def test_set_time_pushes_utc_text() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_time_location_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_time("2026-05-01T18:30:00+00:00")

    dev = client.getDevice(INDI_DEVICE_NAME)
    time_vec = dev.getText("TIME_UTC")
    assert time_vec["UTC"].getText() == "2026-05-01T18:30:00"
    assert time_vec["OFFSET"].getText() == "0"


@pytest.mark.asyncio
async def test_set_location_pushes_geographic_coord() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_time_location_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_location(43.6043, 1.4437)

    dev = client.getDevice(INDI_DEVICE_NAME)
    geo = dev.getNumber("GEOGRAPHIC_COORD")
    assert geo["LAT"].getValue() == pytest.approx(43.6043)
    assert geo["LONG"].getValue() == pytest.approx(1.4437)


def _seed_tracking_property(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "TELESCOPE_TRACK_STATE", {"TRACK_ON": "OFF", "TRACK_OFF": "ON"}
    )


@pytest.mark.asyncio
async def test_set_tracking_true_pushes_track_on_and_publishes_sidereal() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_tracking(True)

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    assert track["TRACK_ON"].getState() == "ON"
    assert track["TRACK_OFF"].getState() == "OFF"
    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"


@pytest.mark.asyncio
async def test_set_tracking_false_pushes_track_off_and_publishes_off() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.set_tracking(True)

    await adapter.set_tracking(False)

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    assert track["TRACK_OFF"].getState() == "ON"
    assert track["TRACK_ON"].getState() == "OFF"
    assert bus.get_full_state().subsystems["tracking"].state == "off"


def _seed_cordwrap_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "CORDWRAP", {"INDI_ENABLED": "OFF", "INDI_DISABLED": "ON"}
    )
    dev.add_switch(
        "CORDWRAP_POS",
        {"CORDWRAP_N": "ON", "CORDWRAP_E": "OFF", "CORDWRAP_S": "OFF", "CORDWRAP_W": "OFF"},
    )


@pytest.mark.asyncio
async def test_cordwrap_set_enabled_true_toggles_indi_enabled_on() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.cordwrap_set_enabled(True)

    cw = client.getDevice(INDI_DEVICE_NAME).getSwitch("CORDWRAP")
    assert cw["INDI_ENABLED"].getState() == "ON"
    assert cw["INDI_DISABLED"].getState() == "OFF"


@pytest.mark.asyncio
async def test_cordwrap_get_enabled_reads_current_state() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    assert await adapter.cordwrap_get_enabled() is False
    await adapter.cordwrap_set_enabled(True)
    assert await adapter.cordwrap_get_enabled() is True


@pytest.mark.asyncio
async def test_cordwrap_set_position_east() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.cordwrap_set_position("E")

    cw_pos = client.getDevice(INDI_DEVICE_NAME).getSwitch("CORDWRAP_POS")
    assert cw_pos["CORDWRAP_E"].getState() == "ON"
    assert cw_pos["CORDWRAP_N"].getState() == "OFF"


@pytest.mark.asyncio
async def test_cordwrap_set_position_invalid_raises() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    with pytest.raises(ValueError):
        await adapter.cordwrap_set_position("Z")


@pytest.mark.asyncio
async def test_cordwrap_get_position_reads_active_cardinal() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.cordwrap_set_position("S")
    assert await adapter.cordwrap_get_position() == "S"


def _seed_backlash_property(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_number(
        "MOUNT_AXIS_BACKLASH",
        {"AZ_POS": 0.0, "AZ_NEG": 0.0, "ALT_POS": 0.0, "ALT_NEG": 0.0},
    )


@pytest.mark.asyncio
async def test_get_backlash_reads_property_element() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    bl = client.getDevice(INDI_DEVICE_NAME).getNumber("MOUNT_AXIS_BACKLASH")
    bl["ALT_POS"].setValue(12.0)

    assert await adapter.get_backlash("alt", "+") == 12


@pytest.mark.asyncio
async def test_set_backlash_writes_property_element() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_backlash("az", "-", 25)

    bl = client.getDevice(INDI_DEVICE_NAME).getNumber("MOUNT_AXIS_BACKLASH")
    assert bl["AZ_NEG"].getValue() == 25.0


@pytest.mark.asyncio
async def test_set_backlash_value_out_of_range_raises() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    with pytest.raises(ValueError):
        await adapter.set_backlash("alt", "+", 150)


@pytest.mark.asyncio
async def test_get_backlash_returns_zero_when_property_absent() -> None:
    """Driver not patched yet — property is absent. Don't crash, return 0."""
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    # Note: no backlash property seeded.
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    assert await adapter.get_backlash("alt", "+") == 0


@pytest.mark.asyncio
async def test_set_backlash_when_property_absent_publishes_error() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    # No backlash property — simulating an unpatched driver.
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_backlash("alt", "+", 5)

    assert bus.get_full_state().subsystems["mount"].state == "error"
