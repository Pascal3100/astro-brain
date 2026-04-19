"""In-memory event bus for the backend's system state.

Semantics:
    * :meth:`StateBus.publish` is synchronous and non-blocking. It mutates
      the in-memory state, recomputes ``overall``, and pushes an
      :class:`Event` to every subscriber's queue. Subscriber queues are
      bounded; when a queue is full, the oldest message is dropped so a
      slow consumer never blocks the producer.
    * :meth:`StateBus.subscribe` returns an async generator. It first
      yields a ``"snapshot"`` event with the current full state, then
      streams ``"update"`` events for every subsequent publish.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from astro_brain.aggregator import compute_overall
from astro_brain.subsystems import SubsystemState
from astro_brain.system_state import SystemState

SUBSCRIBER_QUEUE_MAX = 64


@dataclass
class Event:
    """A broadcast item: a typed envelope around a JSON-serializable payload."""

    type: str  # "snapshot" | "update"
    payload: dict[str, Any]


class StateBus:
    """In-memory, single-process pub/sub hub for system state."""

    def __init__(self) -> None:
        self._subsystems: dict[str, SubsystemState] = {}
        self._seq: int = 0
        self._subscribers: list[asyncio.Queue[Event]] = []

    # --- synchronous public API ------------------------------------------------

    def publish(self, subsystem: str, state: SubsystemState) -> None:
        """Update a subsystem's state and broadcast the change.

        Increments the monotonic ``seq`` and recomputes ``overall`` before
        emitting an ``"update"`` event to every subscriber.
        """
        self._subsystems[subsystem] = state
        self._seq += 1
        full = self.get_full_state()
        event = Event(
            type="update",
            payload={
                "subsystem": subsystem,
                "state": state.to_dict(),
                "overall": full.overall,
                "seq": self._seq,
                "ts": full.ts.isoformat(),
            },
        )
        self._broadcast(event)

    def get_full_state(self) -> SystemState:
        """Return an immutable snapshot of the current system state."""
        return SystemState(
            overall=compute_overall(self._subsystems),
            subsystems=dict(self._subsystems),
            seq=self._seq,
            ts=datetime.now(timezone.utc),
        )

    # --- async subscription ----------------------------------------------------

    async def subscribe(self) -> AsyncIterator[Event]:
        """Stream events: an initial snapshot followed by every update."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
        self._subscribers.append(queue)
        try:
            full = self.get_full_state()
            yield Event(type="snapshot", payload=full.to_dict())
            while True:
                event = await queue.get()
                yield event
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    # --- internal --------------------------------------------------------------

    def _broadcast(self, event: Event) -> None:
        for q in self._subscribers:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)
