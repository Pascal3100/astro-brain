"""Tests for MountIndiAdapter (start/stop, slew, tracking, watchdog)."""

from __future__ import annotations

import asyncio

import pytest

from astro_brain.adapters import mount_indi_adapter
from astro_brain.adapters._indi_property_helpers import SWITCH_OFF, SWITCH_ON
from astro_brain.adapters.mount_indi_adapter import (
    INDI_DEVICE_NAME,
    MountIndiAdapter,
)
from astro_brain.bus import StateBus
from astro_brain.services.interfaces import SensorUnavailableError
from tests.fakes.fake_indi import FakeDevice, FakeIndiClient


def _seed_alive(dev) -> None:
    """Give ``dev`` the property that stands for "the mount answered".

    ``MountIndiAdapter`` waits on ``TELESCOPE_SLEW_RATE`` before publishing
    ``ready``: the driver defines it only once ALT and AZM have replied. A
    fake without it models a mount that is *not* there, so any fake whose
    test expects ``ready`` must carry it.
    """
    dev.add_switch(
        "TELESCOPE_SLEW_RATE",
        {f"{i}x": ("ON" if i == 1 else "OFF") for i in range(1, 9)},
    )


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
    dev.add_switch(
        "PORT_TYPE", {"PORT_AUX_PC": "OFF", "PORT_HC": "ON"}
    )
    _seed_alive(dev)


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
async def test_start_connects_the_driver_to_the_mount() -> None:
    # Regression (journal S38): indiserver advertises the device even while
    # the driver sits at CONNECTION.CONNECT=Off. In that state no mount
    # properties exist and every command silently no-ops — the app's manual
    # mode moved nothing. start() must explicitly push CONNECT=On.
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)  # seeds CONNECTION with CONNECT=OFF
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    conn = client.getDevice(INDI_DEVICE_NAME).getSwitch("CONNECTION")
    assert conn.findWidgetByName("CONNECT").getStateAsString() == "On"
    assert conn.findWidgetByName("DISCONNECT").getStateAsString() == "Off"
    assert any(p is conn for p in client.sent_properties), (
        "start() must send the CONNECTION property to the server"
    )
    assert bus.get_full_state().subsystems["mount"].state == "ready"


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


@pytest.mark.asyncio
async def test_handle_server_disconnected_publishes_disconnected_not_error() -> None:
    # indiserver dropping is a lost link, not a transient command error:
    # publish `disconnected` (what the reconnect supervisor watches) and
    # drop the stale device handle so commands no-op cleanly (S38).
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    assert bus.get_full_state().subsystems["mount"].state == "ready"

    adapter.handle_server_disconnected(2)

    state = bus.get_full_state().subsystems["mount"]
    assert state.state == "disconnected"
    assert "2" in (state.message or "")
    # _device must now be None so a stray slew is a silent no-op.
    await adapter.slew("az", "+", 5)
    assert bus.get_full_state().subsystems["mount"].state == "disconnected"


@pytest.mark.asyncio
async def test_reconnect_reestablishes_link_after_server_drop() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    # Simulate indiserver dropping: transport down + the client callback
    # that the real AstroBrainIndiClient forwards to the adapter.
    client.simulate_disconnect()
    adapter.handle_server_disconnected(1)
    assert client.isServerConnected() is False
    assert bus.get_full_state().subsystems["mount"].state == "disconnected"

    await adapter.reconnect()

    assert client.isServerConnected() is True
    conn = client.getDevice(INDI_DEVICE_NAME).getSwitch("CONNECTION")
    assert conn.findWidgetByName("CONNECT").getStateAsString() == "On"
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_reconnect_republishes_disconnected_on_failure() -> None:
    # A failed reconnect must leave `disconnected` (not `ready`/`error`) so
    # the supervisor keeps retrying.
    bus = StateBus()

    class _NoConnectClient(FakeIndiClient):
        def connectServer(self) -> bool:  # noqa: N802
            return False

    client = _NoConnectClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    # Never started/connected → reconnect must go through connectServer.
    await adapter.reconnect()

    assert bus.get_full_state().subsystems["mount"].state == "disconnected"


@pytest.mark.asyncio
async def test_start_does_not_publish_ready_when_the_mount_never_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression (journal S57): with the mount powered off the driver
    # refuses the link ("Cannot continue without connection to motor
    # controllers") and defines no mount property -- yet CONNECTION.CONNECT
    # still read On, so `ready` went out over a dead mount. A switch state
    # is not evidence; only a driver-published property is.
    monkeypatch.setattr(mount_indi_adapter, "PROPERTY_READY_TIMEOUT_S", 0.3)
    bus = StateBus()
    client = FakeIndiClient()
    dev = client.add_device(INDI_DEVICE_NAME)
    dev.add_switch("CONNECTION", {"CONNECT": "OFF", "DISCONNECT": "ON"})
    # Deliberately no _seed_alive(dev): the mount answers nothing.
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    mount = bus.get_full_state().subsystems["mount"]
    assert mount.state == "error"
    assert "TELESCOPE_SLEW_RATE" in (mount.message or "")


@pytest.mark.asyncio
async def test_ready_needs_more_than_connect_already_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The exact S57 shape: the driver leaves CONNECT=On after a failed open,
    # so _ensure_connected short-circuits on "already connected" and never
    # exercises the link. `ready` must still be withheld.
    monkeypatch.setattr(mount_indi_adapter, "PROPERTY_READY_TIMEOUT_S", 0.3)
    bus = StateBus()
    client = FakeIndiClient()
    dev = client.add_device(INDI_DEVICE_NAME)
    dev.add_switch("CONNECTION", {"CONNECT": "ON", "DISCONNECT": "OFF"})
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.reconnect()

    # `disconnected`, not `error`: the supervisor must keep retrying.
    assert bus.get_full_state().subsystems["mount"].state == "disconnected"


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
    client.sent_properties.clear()  # drop the CONNECTION push from start()

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


class _DelayedConnectionClient(FakeIndiClient):
    """``getDevice`` first returns a placeholder whose ``CONNECTION`` vector
    has no ``CONNECT`` widget yet (nameless widgets, as the real driver
    streams its property tree in after the device is advertised), then the
    fully-populated device. Mirrors journal S38: ``_ensure_connected`` read
    ``CONNECT`` the instant the device appeared and crashed with KeyError.
    """

    def __init__(
        self, placeholder: FakeDevice, full: FakeDevice, ready_after: int
    ) -> None:
        super().__init__()
        self._placeholder = placeholder
        self._full = full
        self._ready_after = ready_after
        self._seen = 0

    def getDevice(self, name: str) -> FakeDevice:  # noqa: N802
        self._seen += 1
        if self._seen > self._ready_after:
            return self._full
        return self._placeholder


@pytest.mark.asyncio
async def test_start_waits_for_connection_widget_to_stream_in() -> None:
    bus = StateBus()
    placeholder = FakeDevice(INDI_DEVICE_NAME)
    # CONNECTION advertised but its named widgets not defined yet (the real
    # driver hands back a nameless placeholder for a beat after connect).
    placeholder.add_switch("CONNECTION", {"": "OFF"})
    full = FakeDevice(INDI_DEVICE_NAME)
    full.add_switch("CONNECTION", {"CONNECT": "OFF", "DISCONNECT": "ON"})
    _seed_alive(full)
    client = _DelayedConnectionClient(placeholder, full, ready_after=2)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    conn = full.getSwitch("CONNECTION")
    assert conn.findWidgetByName("CONNECT").getStateAsString() == "On"
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


@pytest.mark.asyncio
async def test_set_location_waits_for_late_widgets() -> None:
    """Boot race: GEOGRAPHIC_COORD is fetchable before LAT/LONG are named.

    Reproduces the hardware failure of journal S51 — the orchestrator syncs
    the instant ``start()`` publishes ``ready``, while the driver is still
    streaming its property tree, and ``mount`` flipped to ``error`` with the
    message ``'LAT'``. The adapter must wait, not fail.
    """
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    dev = client.getDevice(INDI_DEVICE_NAME)
    # Placeholder vector: present, but without the widgets we write to.
    dev.add_number("GEOGRAPHIC_COORD", {"ELEV": 0.0})
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    async def complete_property() -> None:
        await asyncio.sleep(0.15)
        dev.add_number(
            "GEOGRAPHIC_COORD", {"LAT": 0.0, "LONG": 0.0, "ELEV": 0.0}
        )

    filler = asyncio.create_task(complete_property())
    await adapter.set_location(43.6043, 1.4437)
    await filler

    geo = client.getDevice(INDI_DEVICE_NAME).getNumber("GEOGRAPHIC_COORD")
    assert geo.findWidgetByName("LAT").getValue() == pytest.approx(43.6043)
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_set_location_publishes_error_when_property_never_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely absent property still errors — bounded, not hanging."""
    monkeypatch.setattr(
        mount_indi_adapter, "PROPERTY_READY_TIMEOUT_S", 0.3
    )
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_location(43.6043, 1.4437)

    mount = bus.get_full_state().subsystems["mount"]
    assert mount.state == "error"
    assert "GEOGRAPHIC_COORD" in (mount.message or "")


@pytest.mark.asyncio
async def test_current_position_reads_encoder_angles() -> None:
    """(az, alt) come from TELESCOPE_ENCODER_ANGLES, the mount's own frame."""
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    dev = client.getDevice(INDI_DEVICE_NAME)
    dev.add_number(
        "TELESCOPE_ENCODER_ANGLES", {"AXIS_AZ": 123.45, "AXIS_ALT": -12.5}
    )
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    az, alt = await adapter.current_position()

    assert az == pytest.approx(123.45)
    assert alt == pytest.approx(-12.5)
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_current_position_raises_when_encoders_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mount whose return path is dead must refuse, not return garbage.

    This is the S51 hardware case: the driver connects and accepts commands,
    but never receives a reply, so it never publishes encoder angles. The
    caller needs a refusal it can turn into a 503 — not ``(0, 0)``.
    """
    monkeypatch.setattr(mount_indi_adapter, "PROPERTY_READY_TIMEOUT_S", 0.3)
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    with pytest.raises(SensorUnavailableError):
        await adapter.current_position()

    assert bus.get_full_state().subsystems["mount"].state == "error"


@pytest.mark.asyncio
async def test_current_position_raises_when_device_absent() -> None:
    """Diverges from the other commands: a read cannot silently no-op."""
    bus = StateBus()
    client = FakeIndiClient()  # pas de device seedé
    adapter = MountIndiAdapter(bus, client=client)

    with pytest.raises(SensorUnavailableError):
        await adapter.current_position()


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


@pytest.mark.asyncio
async def test_driver_side_tracking_is_mirrored_on_the_bus() -> None:
    """Le suivi réarmé par le driver doit remonter sur le bus.

    ``INDI::Telescope`` réarme le suivi quand un mouvement manuel s'arrête
    (c'est le comportement voulu : sans suivi le champ défile à l'oculaire).
    On ne publiait ``tracking`` que depuis nos propres commandes, donc
    l'app affichait ``off`` pendant que la monture suivait (journal S57).
    """
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.set_tracking(False)
    assert bus.get_full_state().subsystems["tracking"].state == "off"

    # Le driver réarme le suivi de lui-même, sans goto en cours.
    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    track.findWidgetByName("TRACK_ON").setState(1)
    track.findWidgetByName("TRACK_OFF").setState(0)
    adapter.handle_property_update(track)

    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"
    assert adapter._goto_in_progress is False


@pytest.mark.asyncio
async def test_driver_side_tracking_off_is_mirrored_on_the_bus() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.set_tracking(True)

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    track.findWidgetByName("TRACK_ON").setState(0)
    track.findWidgetByName("TRACK_OFF").setState(1)
    adapter.handle_property_update(track)

    assert bus.get_full_state().subsystems["tracking"].state == "off"


@pytest.mark.asyncio
async def test_identical_track_state_echo_does_not_republish() -> None:
    """Le driver réémet la propriété : pas de churn SSE pour un état égal."""
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.set_tracking(True)
    seq = bus.get_full_state().seq

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    adapter.handle_property_update(track)  # écho identique
    adapter.handle_property_update(track)

    assert bus.get_full_state().seq == seq
    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"


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


# ---------------------------------------------------------------------------
# Configuration du lien série (pont ESP32 filaire sur /dev/ttyAMA0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_configures_serial_link_before_connecting() -> None:
    """Le lien est épinglé en Serial, dans l'ordre, avant CONNECT.

    L'ordre n'est pas cosmétique : le driver ne (re)définit ``DEVICE_PORT``
    qu'une fois en mode Serial, et ne relit ses réglages de lien qu'à
    l'ouverture — donc avant ``CONNECTION.CONNECT``.
    """
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    pushed = [p.getName() for p in client.sent_properties]
    assert pushed[:4] == [
        "CONNECTION_MODE",
        "DEVICE_PORT",
        "PORT_TYPE",
        "CONNECTION",
    ]

    dev = client.getDevice(INDI_DEVICE_NAME)
    mode = dev.getSwitch("CONNECTION_MODE")
    assert mode.findWidgetByName("CONNECTION_SERIAL").getState() == SWITCH_ON
    assert mode.findWidgetByName("CONNECTION_TCP").getState() == SWITCH_OFF
    assert dev.getText("DEVICE_PORT").findWidgetByName("PORT").getText() == (
        "/dev/ttyAMA0"
    )
    port_type = dev.getSwitch("PORT_TYPE")
    assert port_type.findWidgetByName("PORT_AUX_PC").getState() == SWITCH_ON


@pytest.mark.asyncio
async def test_serial_device_can_be_overridden_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ASTRO_BRAIN_SERIAL_DEVICE`` remplace /dev/ttyAMA0 (bench USB)."""
    monkeypatch.setenv("ASTRO_BRAIN_SERIAL_DEVICE", "/dev/ttyUSB0")
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev.getText("DEVICE_PORT").findWidgetByName("PORT").getText() == (
        "/dev/ttyUSB0"
    )


@pytest.mark.asyncio
async def test_start_tolerates_a_device_without_connection_mode() -> None:
    """Un fake nu (aucune propriété de lien) connecte quand même."""
    bus = StateBus()
    client = FakeIndiClient()
    dev = client.add_device(INDI_DEVICE_NAME)
    dev.add_switch("CONNECTION", {"CONNECT": "OFF", "DISCONNECT": "ON"})
    _seed_alive(dev)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    assert [p.getName() for p in client.sent_properties] == ["CONNECTION"]
    assert bus.get_full_state().subsystems["mount"].state == "ready"
