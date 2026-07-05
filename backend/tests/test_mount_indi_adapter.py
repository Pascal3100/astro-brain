"""Tests for MountIndiAdapter (start/stop, slew, tracking, watchdog)."""

from __future__ import annotations

import pytest

from astro_brain.adapters.mount_indi_adapter import (
    INDI_DEVICE_NAME,
    MountIndiAdapter,
)
from astro_brain.bus import StateBus
from tests.fakes.fake_indi import FakeDevice, FakeIndiClient


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
        {f"{i}x": ("ON" if i == 1 else "OFF") for i in range(1, 9)},
    )
    dev.add_switch(
        "TELESCOPE_ABORT_MOTION", {"ABORT": "OFF"}
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
    assert rate_vec.findWidgetByName("4x").getStateAsString() == "On"
    assert rate_vec.findWidgetByName("1x").getStateAsString() == "Off"
    assert motion_ns.findWidgetByName("MOTION_NORTH").getStateAsString() == "On"
    assert motion_ns.findWidgetByName("MOTION_SOUTH").getStateAsString() == "Off"
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
    assert motion_we.findWidgetByName("MOTION_EAST").getStateAsString() == "On"
    assert motion_we.findWidgetByName("MOTION_WEST").getStateAsString() == "Off"


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
    assert motion_ns.findWidgetByName("MOTION_NORTH").getStateAsString() == "Off"
    assert motion_ns.findWidgetByName("MOTION_SOUTH").getStateAsString() == "Off"
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
    assert abort.findWidgetByName("ABORT").getStateAsString() == "On"
    assert bus.get_full_state().subsystems["mount"].state == "ready"


class _StaleDeviceClient(FakeIndiClient):
    """First ``getDevice`` returns an empty device (properties not yet
    defined), later calls return the populated one — mirrors the real
    pyindi behaviour where a device handle cached too early is stale and
    exposes empty property vectors (journal S37).
    """

    def __init__(self, empty: FakeDevice, full: FakeDevice) -> None:
        super().__init__()
        self._empty = empty
        self._full = full
        self._seen = 0

    def getDevice(self, name: str) -> FakeDevice:  # noqa: N802
        self._seen += 1
        return self._empty if self._seen == 1 else self._full


@pytest.mark.asyncio
async def test_slew_refetches_device_not_stale_empty_handle() -> None:
    bus = StateBus()
    empty = FakeDevice(INDI_DEVICE_NAME)  # device known but no properties yet
    full = FakeDevice(INDI_DEVICE_NAME)
    full.add_switch(
        "TELESCOPE_MOTION_WE", {"MOTION_WEST": "OFF", "MOTION_EAST": "OFF"}
    )
    full.add_switch(
        "TELESCOPE_SLEW_RATE",
        {f"{i}x": ("ON" if i == 1 else "OFF") for i in range(1, 9)},
    )
    client = _StaleDeviceClient(empty, full)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()  # a naive adapter caches the empty handle here

    await adapter.slew("az", "+", 8)

    we = full.getSwitch("TELESCOPE_MOTION_WE")
    assert we.findWidgetByName("MOTION_WEST").getStateAsString() == "On"
    assert bus.get_full_state().subsystems["mount"].state == "moving"


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
    assert time_vec.findWidgetByName("UTC").getText() == "2026-05-01T18:30:00"
    assert time_vec.findWidgetByName("OFFSET").getText() == "0"


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
    assert geo.findWidgetByName("LAT").getValue() == pytest.approx(43.6043)
    assert geo.findWidgetByName("LONG").getValue() == pytest.approx(1.4437)


def _seed_sync_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "ON_COORD_SET", {"SLEW": "OFF", "TRACK": "ON", "SYNC": "OFF"}
    )
    dev.add_number("EQUATORIAL_EOD_COORD", {"RA": 0.0, "DEC": 0.0})


@pytest.mark.asyncio
async def test_sync_radec_arms_sync_then_pushes_eod_coord_in_hours() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_sync_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    # Sirius approx (RA 101.287°, DEC -16.716°).
    await adapter.sync_radec(101.287, -16.716)

    dev = client.getDevice(INDI_DEVICE_NAME)
    mode = dev.getSwitch("ON_COORD_SET")
    assert mode.findWidgetByName("SYNC").getStateAsString() == "On"
    assert mode.findWidgetByName("SLEW").getStateAsString() == "Off"
    assert mode.findWidgetByName("TRACK").getStateAsString() == "Off"

    coord = dev.getNumber("EQUATORIAL_EOD_COORD")
    assert coord.findWidgetByName("RA").getValue() == pytest.approx(101.287 / 15.0)
    assert coord.findWidgetByName("DEC").getValue() == pytest.approx(-16.716)


@pytest.mark.asyncio
async def test_sync_radec_publishes_error_when_property_missing() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    # Pas de seed des propriétés sync → ON_COORD_SET introuvable.
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.sync_radec(0.0, 0.0)

    assert bus.get_full_state().subsystems["mount"].state == "error"


@pytest.mark.asyncio
async def test_sync_radec_noop_when_device_absent() -> None:
    bus = StateBus()
    client = FakeIndiClient()  # pas de device seedé
    adapter = MountIndiAdapter(bus, client=client)
    # Pas de start() → _device reste None.

    await adapter.sync_radec(10.0, 20.0)
    # Aucune erreur publiée : silent no-op exigé par le contrat (cf. set_time).


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
    assert track.findWidgetByName("TRACK_ON").getStateAsString() == "On"
    assert track.findWidgetByName("TRACK_OFF").getStateAsString() == "Off"
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
    assert track.findWidgetByName("TRACK_OFF").getStateAsString() == "On"
    assert track.findWidgetByName("TRACK_ON").getStateAsString() == "Off"
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
    assert cw.findWidgetByName("INDI_ENABLED").getStateAsString() == "On"
    assert cw.findWidgetByName("INDI_DISABLED").getStateAsString() == "Off"


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
    assert cw_pos.findWidgetByName("CORDWRAP_E").getStateAsString() == "On"
    assert cw_pos.findWidgetByName("CORDWRAP_N").getStateAsString() == "Off"


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
    bl.findWidgetByName("ALT_POS").setValue(12.0)

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
    assert bl.findWidgetByName("AZ_NEG").getValue() == 25.0


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
