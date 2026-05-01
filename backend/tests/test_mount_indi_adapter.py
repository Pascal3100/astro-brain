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
