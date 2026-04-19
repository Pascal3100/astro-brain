"""Tests for the in-memory ``StateBus`` (pub/sub)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from astro_brain.bus import Event, StateBus
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_fresh_bus_has_empty_subsystems_green_and_seq_zero() -> None:
    bus = StateBus()
    full = bus.get_full_state()
    assert full.overall == "green"
    assert full.subsystems == {}
    assert full.seq == 0


def test_publish_updates_subsystem_and_increments_seq() -> None:
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    full = bus.get_full_state()
    assert full.subsystems["mount"].state == "ready"
    assert full.seq == 1
    assert full.overall == "green"


def test_publish_recomputes_overall() -> None:
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="error", since=_now()))
    assert bus.get_full_state().overall == "red"


async def test_subscribe_yields_initial_snapshot() -> None:
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    agen = bus.subscribe()
    first = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert first.type == "snapshot"
    assert first.payload["subsystems"]["mount"]["state"] == "ready"
    await agen.aclose()


async def test_subscribe_yields_updates_after_publish() -> None:
    bus = StateBus()
    agen = bus.subscribe()
    snapshot = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert snapshot.type == "snapshot"

    bus.publish("gps", SubsystemState(state="fix_3d", since=_now()))
    event = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert event.type == "update"
    assert event.payload["subsystem"] == "gps"
    assert event.payload["state"]["state"] == "fix_3d"
    assert event.payload["seq"] == 1
    await agen.aclose()


async def test_multiple_subscribers_each_get_updates() -> None:
    bus = StateBus()
    a = bus.subscribe()
    b = bus.subscribe()
    await asyncio.wait_for(a.__anext__(), timeout=1.0)  # snapshot
    await asyncio.wait_for(b.__anext__(), timeout=1.0)  # snapshot

    bus.publish("system", SubsystemState(state="ok", since=_now()))
    ea = await asyncio.wait_for(a.__anext__(), timeout=1.0)
    eb = await asyncio.wait_for(b.__anext__(), timeout=1.0)
    assert ea.type == "update"
    assert eb.type == "update"
    assert ea.payload["seq"] == 1
    assert eb.payload["seq"] == 1
    await a.aclose()
    await b.aclose()


async def test_unsubscribe_is_clean() -> None:
    bus = StateBus()
    agen = bus.subscribe()
    await asyncio.wait_for(agen.__anext__(), timeout=1.0)  # snapshot
    await agen.aclose()
    # publishing after unsubscribe must not raise
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    assert bus.get_full_state().seq == 1


def test_event_dataclass_has_type_and_payload() -> None:
    event = Event(type="snapshot", payload={"hello": "world"})
    assert event.type == "snapshot"
    assert event.payload == {"hello": "world"}
