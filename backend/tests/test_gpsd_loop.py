"""Tests for the :class:`GpsdAdapter` poll loop.

The loop runs against a stand-in for the ``gpsd`` module injected into
``sys.modules`` (the adapter imports it lazily inside :meth:`start` /
:meth:`_loop`, so the injection is picked up).

The fake serves one *sticky* outcome: it keeps returning the same packet —
or raising the same error — until the test swaps it. Tests therefore drive
transitions explicitly and never race the poll interval.

Focus:
    * ``UserWarning('GPS not active')`` — what ``gpsd-py3`` raises whenever
      the daemon reports ``mode < 1`` — is the nominal no-fix state and must
      go through the normal publish path, not the error path.
    * logging is per state transition, not per poll iteration.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import Callable
from typing import Any

import pytest

from astro_brain.adapters import gpsd_adapter
from astro_brain.adapters.gpsd_adapter import GpsdAdapter
from astro_brain.bus import StateBus

NO_FIX = UserWarning("GPS not active")


class _Packet:
    """Minimal stand-in for a ``gpsd`` TPV packet."""

    def __init__(self, mode: int, sats: int = 0) -> None:
        self.mode = mode
        self.sats_valid = sats
        self.hdop = 0.9

    def position(self) -> tuple[float, float]:
        return (43.6, 1.44)

    def altitude(self) -> float:
        return 150.0


class _FakeGpsd:
    """``gpsd`` module stub returning a sticky outcome the test controls."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls = 0

    def connect(self) -> None:
        pass

    def get_current(self) -> Any:
        self.calls += 1
        outcome = self.outcome
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse the poll interval and detail throttle so tests stay quick."""
    monkeypatch.setattr(gpsd_adapter, "POLL_INTERVAL_S", 0.002)
    monkeypatch.setattr(gpsd_adapter, "DETAIL_THROTTLE_S", 0.0)


def _install(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> _FakeGpsd:
    fake = _FakeGpsd(outcome)
    monkeypatch.setitem(sys.modules, "gpsd", fake)
    return fake


def _gps_state(bus: StateBus) -> str:
    return bus.get_full_state().subsystems["gps"].state


async def _until(what: str, pred: Callable[[], bool], timeout_s: float = 3.0) -> None:
    """Yield control until ``pred`` holds, failing the test on timeout."""
    deadline = time.monotonic() + timeout_s
    while not pred():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out waiting for {what}")
        await asyncio.sleep(0.002)


async def _polls(fake: _FakeGpsd, n: int) -> None:
    """Let the loop run ``n`` further polls against the current outcome."""
    target = fake.calls + n
    await _until(f"{n} more polls", lambda: fake.calls >= target)


async def test_losing_the_fix_republishes_and_clears_the_position(
    monkeypatch: pytest.MonkeyPatch, fast_poll: None
) -> None:
    """A fix followed by 'GPS not active' must not leave the state frozen.

    Regression: the UserWarning used to be caught as a transient error, so
    the loop skipped the publish entirely — the bus kept reporting ``fix_3d``
    and ``latest_fix()`` kept serving a stale position.
    """
    fake = _install(monkeypatch, _Packet(mode=3, sats=8))
    bus = StateBus()
    adapter = GpsdAdapter(bus)

    await adapter.start()
    try:
        await _until("the 3D fix", lambda: _gps_state(bus) == "fix_3d")
        assert adapter.latest_fix() is not None

        fake.outcome = NO_FIX
        await _until("the fix to clear", lambda: adapter.latest_fix() is None)
        # satellites stay sticky, so losing the fix reads as "searching"
        assert _gps_state(bus) == "searching"
    finally:
        await adapter.stop()


async def test_no_fix_is_not_logged_as_an_error(
    monkeypatch: pytest.MonkeyPatch, fast_poll: None, caplog: pytest.LogCaptureFixture
) -> None:
    """A permanent no-fix must not emit a warning per poll."""
    fake = _install(monkeypatch, NO_FIX)
    adapter = GpsdAdapter(StateBus())

    with caplog.at_level(logging.DEBUG, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _polls(fake, 12)
        finally:
            await adapter.stop()

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], f"no-fix logged {len(warnings)} warning(s)"


async def test_state_transitions_are_logged_once_each(
    monkeypatch: pytest.MonkeyPatch, fast_poll: None, caplog: pytest.LogCaptureFixture
) -> None:
    """One log line per state change, regardless of how many polls run."""
    fake = _install(monkeypatch, _Packet(mode=3, sats=8))
    bus = StateBus()
    adapter = GpsdAdapter(bus)

    def transitions() -> list[logging.LogRecord]:
        return [r for r in caplog.records if "gps state" in r.message]

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _until("the 3D fix", lambda: _gps_state(bus) == "fix_3d")
            await _polls(fake, 8)  # stay on the fix: no further logging
            assert len(transitions()) == 1

            fake.outcome = NO_FIX
            await _until("the fix to clear", lambda: adapter.latest_fix() is None)
            await _polls(fake, 8)  # stay no-fix: still no further logging
        finally:
            await adapter.stop()

    # exactly two transitions: no_fix -> fix_3d -> searching
    assert len(transitions()) == 2, [r.getMessage() for r in transitions()]


async def test_real_poll_errors_are_logged_once_per_episode(
    monkeypatch: pytest.MonkeyPatch, fast_poll: None, caplog: pytest.LogCaptureFixture
) -> None:
    """A genuine, repeating gpsd failure warns once — then stays quiet."""
    fake = _install(monkeypatch, ConnectionResetError("gpsd went away"))
    adapter = GpsdAdapter(StateBus())

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _polls(fake, 12)
        finally:
            await adapter.stop()

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1, f"{len(warnings)} warnings for one failure episode"


async def test_recovery_after_an_error_episode_is_logged_and_rearms(
    monkeypatch: pytest.MonkeyPatch, fast_poll: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Recovering re-arms the warning so a later episode is reported again."""
    fake = _install(monkeypatch, ConnectionResetError("boom"))
    adapter = GpsdAdapter(StateBus())

    def warnings() -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.levelno >= logging.WARNING]

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _until("the first warning", lambda: len(warnings()) == 1)

            fake.outcome = _Packet(mode=3, sats=8)
            await _until(
                "the recovery log",
                lambda: any("recovered" in r.message for r in caplog.records),
            )

            fake.outcome = ConnectionResetError("boom again")
            await _until("the second warning", lambda: len(warnings()) == 2)
        finally:
            await adapter.stop()

    assert len(warnings()) == 2
