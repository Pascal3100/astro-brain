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
