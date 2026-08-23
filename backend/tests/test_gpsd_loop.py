"""Tests for the :class:`GpsdAdapter` streaming loop.

The loop runs against a **fake gpsd daemon**: a real TCP server on
``127.0.0.1`` that greets with a VERSION line, records the watch command
it receives and replays the JSON reports a test pushes. The adapter takes
``host`` / ``port``, so nothing is monkeypatched into the socket layer.

Focus:
    * the watch command must enable ``json`` — the whole point of journal
      S51: gpsd's ``?POLL;`` answer has no satellite count, only a
      streamed SKY report does;
    * satellites come from SKY, the fix from TPV, and the two are combined;
    * losing the fix, a silent stream and a dropped connection all clear
      the position instead of freezing it;
    * logging is per state transition / per failure episode, not per report.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import pytest

from astro_brain.adapters import gpsd_adapter
from astro_brain.adapters.gpsd_adapter import GpsdAdapter
from astro_brain.bus import StateBus

VERSION = {"class": "VERSION", "release": "3.25", "proto_major": 3}


class _FakeGpsd:
    """Minimal gpsd stand-in: greets, records the watch, replays reports."""

    def __init__(self) -> None:
        self._server: asyncio.AbstractServer | None = None
        self.port = 0
        self.watches: list[str] = []
        self._writers: list[asyncio.StreamWriter] = []

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for w in self._writers:
            w.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        writer.write(json.dumps(VERSION).encode() + b"\n")
        await writer.drain()
        watch = await reader.readline()
        self.watches.append(watch.decode().strip())
        self._writers.append(writer)
        await reader.read()  # hold the session open until the client leaves

    async def push(self, report: dict[str, Any]) -> None:
        """Send one JSON report to every connected client."""
        line = json.dumps(report).encode() + b"\n"
        for w in list(self._writers):
            w.write(line)
            await w.drain()

    async def hang_up(self) -> None:
        """Close the client connections, as a restarting gpsd would."""
        for w in list(self._writers):
            w.close()
        self._writers.clear()


def _tpv(mode: int, **extra: Any) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "class": "TPV",
        "device": "/dev/serial0",
        "mode": mode,
    }
    if mode >= 2:
        packet |= {"lat": 43.6, "lon": 1.44}
    if mode == 3:
        packet["altMSL"] = 150.0
    return packet | extra


def _sky(seen: int, used: int) -> dict[str, Any]:
    return {
        "class": "SKY",
        "device": "/dev/serial0",
        "nSat": seen,
        "uSat": used,
        "hdop": 0.9,
    }


@pytest.fixture
def fast_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse the throttle and the reconnect delay so tests stay quick."""
    monkeypatch.setattr(gpsd_adapter, "DETAIL_THROTTLE_S", 0.0)
    monkeypatch.setattr(gpsd_adapter, "RECONNECT_DELAY_S", 0.01)


@pytest.fixture
async def daemon() -> Any:
    fake = _FakeGpsd()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()


def _gps(bus: StateBus) -> Any:
    return bus.get_full_state().subsystems["gps"]


async def _until(what: str, pred: Callable[[], bool], timeout_s: float = 3.0) -> None:
    """Yield control until ``pred`` holds, failing the test on timeout."""
    deadline = time.monotonic() + timeout_s
    while not pred():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out waiting for {what}")
        await asyncio.sleep(0.005)


async def test_watch_command_enables_json_streaming(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    """Regression: a watch without ``json`` streams nothing (journal S51).

    ``gpsd-py3`` sent ``?WATCH={"enable":true}``, got ``json:false`` back
    and fell back to ``?POLL;`` — whose SKY object carries the DOPs but no
    ``satellites`` / ``nSat`` / ``uSat``. Hence the count stuck at 0.
    """
    adapter = GpsdAdapter(StateBus(), host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
    finally:
        await adapter.stop()

    assert json.loads(daemon.watches[0].removeprefix("?WATCH=").rstrip(";")) == {
        "enable": True,
        "json": True,
    }


async def test_sky_report_publishes_the_real_satellite_count(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=15, used=9))
        await _until(
            "the satellite count",
            lambda: _gps(bus).details.get("satellites") == 9,
        )
        details = _gps(bus).details
        assert details["satellites_visible"] == 15
        assert details["hdop"] == pytest.approx(0.9)
    finally:
        await adapter.stop()


async def test_a_dop_only_sky_does_not_erase_the_satellite_count(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    """gpsd alternates a full SKY and a DOP-only one (measured on 3.25).

    Retaining the last SKY wholesale zeroed the count every other report,
    and the 1 s publish throttle landed on the empty ones.
    """
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=24, used=14))
        await _until(
            "the satellite count",
            lambda: _gps(bus).details.get("satellites") == 14,
        )
        await daemon.push({"class": "SKY", "device": "/dev/serial0", "hdop": 0.92})
        await asyncio.sleep(0.05)
        details = _gps(bus).details
        assert details["satellites"] == 14
        assert details["satellites_visible"] == 24
        assert details["hdop"] == pytest.approx(0.92)  # the DOP did refresh
    finally:
        await adapter.stop()


async def test_satellites_seen_without_a_fix_reads_as_searching(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    """``searching`` was unreachable while the count was always 0."""
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=6, used=0))
        await daemon.push(_tpv(mode=1))
        await _until("searching", lambda: _gps(bus).state == "searching")
        assert adapter.latest_fix() is None
    finally:
        await adapter.stop()


async def test_tpv_and_sky_are_combined_into_a_3d_fix(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=12, used=8))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: _gps(bus).state == "fix_3d")
        details = _gps(bus).details
        assert details["lat"] == pytest.approx(43.6)
        assert details["altitude_m"] == pytest.approx(150.0)
        assert details["satellites"] == 8  # SKY survives the TPV report
        fix = adapter.latest_fix()
        assert fix is not None and fix.is_3d
    finally:
        await adapter.stop()


async def test_losing_the_fix_clears_the_position(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    """A fix followed by ``mode=1`` must not leave a stale position served."""
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=12, used=8))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: adapter.latest_fix() is not None)

        await daemon.push(_tpv(mode=1))
        await _until("the fix to clear", lambda: adapter.latest_fix() is None)
        # satellites are still seen, so the mount is "searching", not blind
        assert _gps(bus).state == "searching"
    finally:
        await adapter.stop()


async def test_a_stale_tpv_expires_even_while_sky_keeps_coming(
    daemon: _FakeGpsd, fast_loop: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fix must expire on its own age, not only on stream silence.

    gpsd emits SKY at 1 Hz whether or not there is a fix, so the readline
    deadline never fires while satellites keep arriving. A receiver that
    stops reporting positions while still reporting satellites would
    otherwise leave the last fix frozen — and re-stamped as current on
    every SKY — which the orchestrator syncs to the mount and the wizard
    uses as the observer position.
    """
    monkeypatch.setattr(gpsd_adapter, "FIX_TIMEOUT_S", 0.02)
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=12, used=8))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: adapter.latest_fix() is not None)

        # No further TPV. The stream stays alive on SKY alone, so the
        # readline deadline never fires — only the fix's own age can.
        await asyncio.sleep(0.1)
        await daemon.push(_sky(seen=12, used=8))
        await _until("the fix to expire", lambda: adapter.latest_fix() is None)
        # satellites are still seen, so this is "searching", not blind
        assert _gps(bus).state == "searching"
        assert _gps(bus).details["satellites_visible"] == 12
    finally:
        await adapter.stop()


async def test_a_fix_is_stamped_with_its_tpv_arrival_not_the_publish_time(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    """``GpsFix.timestamp`` must date the position, not the last SKY."""
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: adapter.latest_fix() is not None)
        fix = adapter.latest_fix()
        assert fix is not None
        stamped = fix.timestamp

        await asyncio.sleep(0.05)
        await daemon.push(_sky(seen=12, used=8))
        await _until(
            "the satellite count",
            lambda: _gps(bus).details.get("satellites_visible") == 12,
        )
        again = adapter.latest_fix()
        assert again is not None
        assert again.timestamp == stamped
    finally:
        await adapter.stop()


async def test_a_silent_stream_clears_the_fix(
    daemon: _FakeGpsd, fast_loop: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gpsd up but mute (receiver unplugged) must not freeze the last fix."""
    monkeypatch.setattr(gpsd_adapter, "STALE_TIMEOUT_S", 0.05)
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the watch command", lambda: bool(daemon.watches))
        await daemon.push(_sky(seen=12, used=8))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: adapter.latest_fix() is not None)

        await _until("the stale timeout", lambda: adapter.latest_fix() is None)
        assert _gps(bus).state == "no_fix"
    finally:
        await adapter.stop()


async def test_reconnects_after_gpsd_hangs_up(
    daemon: _FakeGpsd, fast_loop: None
) -> None:
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)
    await adapter.start()
    try:
        await _until("the first watch", lambda: len(daemon.watches) == 1)
        await daemon.push(_sky(seen=12, used=8))
        await daemon.push(_tpv(mode=3))
        await _until("the 3D fix", lambda: adapter.latest_fix() is not None)

        await daemon.hang_up()
        await _until("the second watch", lambda: len(daemon.watches) == 2)
        # the dropped session must not leave a stale position behind
        assert adapter.latest_fix() is None
    finally:
        await adapter.stop()


async def test_state_transitions_are_logged_once_each(
    daemon: _FakeGpsd, fast_loop: None, caplog: pytest.LogCaptureFixture
) -> None:
    """One log line per state change, however many reports arrive."""
    bus = StateBus()
    adapter = GpsdAdapter(bus, host="127.0.0.1", port=daemon.port)

    def transitions() -> list[logging.LogRecord]:
        return [r for r in caplog.records if "gps state" in r.message]

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _until("the watch command", lambda: bool(daemon.watches))
            await daemon.push(_sky(seen=12, used=8))
            await daemon.push(_tpv(mode=3))
            await _until("the 3D fix", lambda: _gps(bus).state == "fix_3d")
            # SKY lands before TPV, so the pass through ``searching`` is real
            assert len(transitions()) == 2
            for _ in range(8):  # stay on the fix: no further logging
                await daemon.push(_tpv(mode=3))
            await asyncio.sleep(0.05)  # let them all be ingested
            await daemon.push(_tpv(mode=1))
            await _until("searching", lambda: _gps(bus).state == "searching")
        finally:
            await adapter.stop()

    # no_fix -> searching -> fix_3d -> searching, and nothing else
    assert len(transitions()) == 3, [r.getMessage() for r in transitions()]


async def test_connection_failures_are_logged_once_per_episode(
    fast_loop: None, caplog: pytest.LogCaptureFixture
) -> None:
    """gpsd down warns once, then stays quiet across every retry."""
    # Bind then release a port so connecting to it is refused, not hung.
    probe = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = probe.sockets[0].getsockname()[1]
    probe.close()
    await probe.wait_closed()

    adapter = GpsdAdapter(StateBus(), host="127.0.0.1", port=port)

    def warnings() -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.levelno >= logging.WARNING]

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        await adapter.start()
        try:
            await _until("the first warning", lambda: len(warnings()) == 1)
            await asyncio.sleep(0.15)  # several further retries
        finally:
            await adapter.stop()

    assert len(warnings()) == 1, [r.getMessage() for r in warnings()]


async def test_recovery_after_an_outage_is_logged_and_rearms(
    daemon: _FakeGpsd, fast_loop: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Recovering re-arms the warning so a later episode is reported again."""
    adapter = GpsdAdapter(StateBus(), host="127.0.0.1", port=daemon.port)

    def warnings() -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.levelno >= logging.WARNING]

    with caplog.at_level(logging.INFO, logger=gpsd_adapter.__name__):
        # start against the live daemon, then take it away
        await adapter.start()
        try:
            await _until("the first watch", lambda: bool(daemon.watches))
            await daemon.stop()
            await _until("the outage warning", lambda: len(warnings()) == 1)

            await daemon.start()  # a new port: point the adapter at it
            adapter._port = daemon.port  # noqa: SLF001 - test-only rewiring
            await _until(
                "the recovery log",
                lambda: any("recovered" in r.message for r in caplog.records),
            )
        finally:
            await adapter.stop()

    assert len(warnings()) == 1
