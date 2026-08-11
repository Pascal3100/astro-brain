"""Background supervisor that keeps the mount link alive.

Mirrors :class:`Orchestrator` / :class:`AlignmentInvalidator`: a task
subscribed to the :class:`StateBus` that reacts to mount state. When the
mount reports ``disconnected`` — published by the adapter when indiserver
drops (:meth:`MountIndiAdapter.handle_server_disconnected`) or when a
connect attempt fails — it drives :meth:`MountService.reconnect` with
exponential back-off until the mount is ``ready`` again.

``error`` is deliberately ignored: it marks a recoverable command failure
(the driver is still connected), not a lost link. A manual
``POST /mount/reconnect`` calls ``reconnect()`` directly; this loop simply
observes the resulting ``ready`` and stops retrying. See journal S38.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from astro_brain.bus import StateBus, iter_state_snapshots
from astro_brain.services.interfaces import MountService
from astro_brain.subsystems import MountState

logger = logging.getLogger(__name__)

DEFAULT_BACKOFF_S: tuple[float, ...] = (1, 2, 5, 10, 30)


class MountConnectionSupervisor:
    """Reconnects the mount with back-off whenever the link drops."""

    def __init__(
        self,
        *,
        bus: StateBus,
        mount: MountService,
        backoff: Sequence[float] = DEFAULT_BACKOFF_S,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._bus = bus
        self._mount = mount
        self._backoff = tuple(backoff) or (1.0,)
        self._sleep = sleep if sleep is not None else asyncio.sleep

    async def run(self) -> None:
        """Consume bus events and recover the mount until cancelled."""
        async for subsystems in iter_state_snapshots(self._bus):
            mount = subsystems.get("mount")
            if mount is not None and mount.state == MountState.DISCONNECTED.value:
                await self._recover()

    async def _recover(self) -> None:
        """Retry ``reconnect()`` with back-off until the mount is ready.

        Returns early if the mount leaves ``disconnected`` by any other
        means (e.g. a manual reconnect succeeded meanwhile).
        """
        attempt = 0
        while True:
            mount = self._bus.get_full_state().subsystems.get("mount")
            if mount is None or mount.state != MountState.DISCONNECTED.value:
                return
            # WARNING (not INFO): the backend runs at the WARNING root level
            # in production, so INFO would be invisible — and a lost mount
            # link + its recovery are exactly the events ops needs to see.
            logger.warning(
                "mount supervisor: reconnect attempt %d", attempt + 1
            )
            await self._mount.reconnect()
            mount = self._bus.get_full_state().subsystems.get("mount")
            if mount is not None and mount.state == MountState.READY.value:
                logger.warning("mount supervisor: reconnected")
                return
            delay = self._backoff[min(attempt, len(self._backoff) - 1)]
            attempt += 1
            await self._sleep(delay)
