"""Tests for the boot orchestrator (mount + gps → set_time / set_location)."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.services.interfaces import GpsFix
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(UTC)


class _StubGps:
    """Minimal :class:`GpsSource` stub — injects a fixed lat/lon."""

    def __init__(self, fix: GpsFix | None = None) -> None:
        self._fix = fix

    def latest_fix(self) -> GpsFix | None:
        return self._fix


async def _run_briefly(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    """Start ``coro`` as a task and let it do its first iteration."""
    task = asyncio.create_task(coro)
    await asyncio.sleep(0.05)
    return task


async def _stop_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_orchestrator_syncs_when_mount_ready_and_gps_fix() -> None:
    bus = StateBus()
    mount = AsyncMock()
    # Stub lat/lon deliberately differ from anything published in bus
    # details, so the assertion can only pass if the sync reads from the
    # typed source rather than the bus.
    gps = _StubGps(GpsFix(lat=10.111, lon=20.222, timestamp=_now(), is_3d=True))
    orch = Orchestrator(bus=bus, mount=mount, gps=gps)

    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 48.85, "lon": 2.35},
            since=_now(),
        ),
    )

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 1
    assert mount.set_location.call_count == 1
    (lat, lon), _ = mount.set_location.call_args
    assert lat == 10.111 and lon == 20.222

    await _stop_task(task)


async def test_orchestrator_does_not_sync_with_no_fix() -> None:
    bus = StateBus()
    mount = AsyncMock()
    gps = _StubGps(None)
    orch = Orchestrator(bus=bus, mount=mount, gps=gps)

    bus.publish("gps", SubsystemState(state="no_fix", since=_now()))
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 0
    assert mount.set_location.call_count == 0

    await _stop_task(task)


async def test_orchestrator_does_not_sync_when_trigger_armed_but_no_typed_fix() -> None:
    """Bus reports a fix (trigger armed) but the typed source has none yet."""
    bus = StateBus()
    mount = AsyncMock()
    gps = _StubGps(None)
    orch = Orchestrator(bus=bus, mount=mount, gps=gps)

    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 48.85, "lon": 2.35},
            since=_now(),
        ),
    )
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 0
    assert mount.set_location.call_count == 0

    await _stop_task(task)


async def test_orchestrator_syncs_only_once_while_conditions_hold() -> None:
    bus = StateBus()
    mount = AsyncMock()
    gps = _StubGps(GpsFix(lat=1.0, lon=2.0, timestamp=_now(), is_3d=True))
    orch = Orchestrator(bus=bus, mount=mount, gps=gps)

    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 1.0, "lon": 2.0},
            since=_now(),
        ),
    )
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)

    # extra publishes that do NOT break the conditions should not resync
    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 1.0, "lon": 2.0, "satellites": 9},
            since=_now(),
        ),
    )
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    await _stop_task(task)


async def test_orchestrator_resyncs_after_disconnect_reconnect() -> None:
    bus = StateBus()
    mount = AsyncMock()
    gps = _StubGps(GpsFix(lat=1.0, lon=2.0, timestamp=_now(), is_3d=True))
    orch = Orchestrator(bus=bus, mount=mount, gps=gps)

    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 1.0, "lon": 2.0},
            since=_now(),
        ),
    )
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    # break the condition, then restore it
    bus.publish("mount", SubsystemState(state="disconnected", since=_now()))
    await asyncio.sleep(0.05)
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 2

    await _stop_task(task)
