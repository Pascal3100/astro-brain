"""Tests du boot orchestrator (monture ready → set_location / set_time)."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(UTC)


class _StubPosition:
    """Provider de position minimal — renvoie un site fixe (ou aucun)."""

    def __init__(self, pos: tuple[float, float] | None = None) -> None:
        self._pos = pos

    def position(self) -> tuple[float, float] | None:
        return self._pos


async def _run_briefly(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    """Start ``coro`` as a task and let it do its first iteration."""
    task = asyncio.create_task(coro)
    await asyncio.sleep(0.05)
    return task


async def _stop_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def _orch(bus: StateBus, mount: AsyncMock, *, pos=None, clock: bool = True):
    return Orchestrator(
        bus=bus,
        mount=mount,
        position=_StubPosition(pos),
        clock_synced=lambda: clock,
    )


async def test_syncs_when_mount_becomes_ready() -> None:
    """La monture prête suffit : plus aucune dépendance à un fix GPS."""
    bus = StateBus()
    mount = AsyncMock()
    orch = _orch(bus, mount, pos=(10.111, 20.222))

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 1
    assert mount.set_location.call_count == 1
    (lat, lon), _ = mount.set_location.call_args
    assert (lat, lon) == (10.111, 20.222)

    await _stop_task(task)


async def test_no_location_pushed_without_a_known_site() -> None:
    """Pas de site ⇒ pas de position, mais l'heure part quand même."""
    bus = StateBus()
    mount = AsyncMock()
    orch = _orch(bus, mount, pos=None)

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_location.call_count == 0
    assert mount.set_time.call_count == 1

    await _stop_task(task)


async def test_time_is_not_pushed_when_the_clock_is_not_synced() -> None:
    """Le défaut latent corrigé : `fake-hwclock` restitue l'heure du dernier arrêt."""
    bus = StateBus()
    mount = AsyncMock()
    orch = _orch(bus, mount, pos=(1.0, 2.0), clock=False)

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 0
    assert mount.set_location.call_count == 1

    await _stop_task(task)


async def test_nothing_pushed_stays_armed_until_the_clock_catches_up() -> None:
    """Ni site ni horloge : on reste armé, et la sync part dès que l'horloge suit."""
    bus = StateBus()
    mount = AsyncMock()
    clock = {"synced": False}
    orch = Orchestrator(
        bus=bus,
        mount=mount,
        position=_StubPosition(None),
        clock_synced=lambda: clock["synced"],
    )

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 0

    clock["synced"] = True
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    await _stop_task(task)


async def test_syncs_only_once_while_the_mount_stays_ready() -> None:
    bus = StateBus()
    mount = AsyncMock()
    orch = _orch(bus, mount, pos=(1.0, 2.0))

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)

    # une publication qui ne casse pas la condition ne doit pas resynchroniser
    bus.publish("system", SubsystemState(state="ok", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    await _stop_task(task)


async def test_resyncs_after_disconnect_reconnect() -> None:
    bus = StateBus()
    mount = AsyncMock()
    orch = _orch(bus, mount, pos=(1.0, 2.0))

    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    bus.publish("mount", SubsystemState(state="disconnected", since=_now()))
    await asyncio.sleep(0.05)
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 2

    await _stop_task(task)
