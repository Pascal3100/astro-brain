"""Tests goto_radec + détection de fin de slew du MountIndiAdapter."""
from __future__ import annotations

import pytest

from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter
from astro_brain.bus import StateBus
from tests.fakes.fake_indi import FakeIndiClient


def _adapter_with_device() -> tuple[MountIndiAdapter, FakeIndiClient]:
    client = FakeIndiClient()
    dev = client.add_device("Celestron AUX")
    dev.add_switch("ON_COORD_SET", {"SLEW": "OFF", "TRACK": "OFF", "SYNC": "OFF"})
    dev.add_number("EQUATORIAL_EOD_COORD", {"RA": 0.0, "DEC": 0.0})
    adapter = MountIndiAdapter(StateBus(), client=client)
    return adapter, client


@pytest.mark.asyncio
async def test_goto_radec_arms_track_and_pushes_coords():
    adapter, client = _adapter_with_device()
    await adapter.start()
    client.sent_properties.clear()

    await adapter.goto_radec(101.287, -16.716, target_name="Sirius")

    coord_set = client.getDevice("Celestron AUX").getSwitch("ON_COORD_SET")
    assert coord_set["TRACK"].getState() == "ON"
    assert coord_set["SYNC"].getState() == "OFF"
    coord = client.getDevice("Celestron AUX").getNumber("EQUATORIAL_EOD_COORD")
    assert coord["RA"].getValue() == pytest.approx(101.287 / 15.0)
    assert coord["DEC"].getValue() == pytest.approx(-16.716)


@pytest.mark.asyncio
async def test_goto_radec_publishes_moving_with_goto_details():
    adapter, _ = _adapter_with_device()
    await adapter.start()
    await adapter.goto_radec(101.287, -16.716, target_name="Sirius")

    mount = adapter._bus.get_full_state().subsystems["mount"]
    assert mount.state == "moving"
    assert mount.details["goto_in_progress"] is True
    assert mount.details["goto"]["target_name"] == "Sirius"


@pytest.mark.asyncio
async def test_goto_radec_noop_when_device_absent():
    adapter = MountIndiAdapter(StateBus(), client=FakeIndiClient())
    await adapter.goto_radec(10.0, 10.0, target_name="X")  # ne lève pas


@pytest.mark.asyncio
async def test_fake_mount_goto_records_call_and_publishes():
    from astro_brain.services.fakes import FakeMount

    bus = StateBus()
    mount = FakeMount(bus)
    await mount.goto_radec(101.0, -16.0, target_name="Sirius")
    assert mount.goto_calls == [(101.0, -16.0, "Sirius")]
    state = bus.get_full_state().subsystems["mount"]
    assert state.state == "moving"
    assert state.details["goto_in_progress"] is True
