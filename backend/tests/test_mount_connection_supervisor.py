"""Tests for MountConnectionSupervisor (auto-reconnect on server drop)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from astro_brain.bus import StateBus
from astro_brain.mount_connection_supervisor import MountConnectionSupervisor
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(UTC)


class _FlakyMount:
    """Fails ``fail_times`` reconnects (publishes ``disconnected``), then OK."""

    def __init__(self, bus: StateBus, fail_times: int) -> None:
        self._bus = bus
        self._fail = fail_times
        self.calls = 0

    async def reconnect(self) -> None:
        self.calls += 1
        state = "disconnected" if self.calls <= self._fail else "ready"
        self._bus.publish("mount", SubsystemState(state=state, since=_now()))


async def _noop_sleep(_delay: float) -> None:
    return None


@pytest.mark.asyncio
async def test_supervisor_retries_with_backoff_until_ready() -> None:
    bus = StateBus()
    mount = _FlakyMount(bus, fail_times=2)
    sup = MountConnectionSupervisor(
        bus=bus, mount=mount, backoff=(0,), sleep=_noop_sleep
    )
    bus.publish("mount", SubsystemState(state="disconnected", since=_now()))

    task = asyncio.create_task(sup.run())
    for _ in range(20):
        await asyncio.sleep(0)
        if bus.get_full_state().subsystems["mount"].state == "ready":
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert mount.calls == 3  # 2 failures + 1 success
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_supervisor_idle_while_mount_ready() -> None:
    bus = StateBus()
    mount = _FlakyMount(bus, fail_times=0)
    sup = MountConnectionSupervisor(
        bus=bus, mount=mount, backoff=(0,), sleep=_noop_sleep
    )
    bus.publish("mount", SubsystemState(state="ready", since=_now()))

    task = asyncio.create_task(sup.run())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert mount.calls == 0


@pytest.mark.asyncio
async def test_supervisor_ignores_transient_error_state() -> None:
    # `error` is a recoverable command failure (driver still connected):
    # the supervisor must NOT try to reconnect on it.
    bus = StateBus()
    mount = _FlakyMount(bus, fail_times=0)
    sup = MountConnectionSupervisor(
        bus=bus, mount=mount, backoff=(0,), sleep=_noop_sleep
    )
    bus.publish("mount", SubsystemState(state="error", since=_now()))

    task = asyncio.create_task(sup.run())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert mount.calls == 0
