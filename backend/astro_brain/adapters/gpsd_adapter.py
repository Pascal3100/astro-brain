"""Gpsd adapter for the DroTek GPS module.

Talks the gpsd JSON protocol directly over TCP (``127.0.0.1:2947``) with
:mod:`asyncio` streams — no third-party client, so nothing to install and
the module is importable on a workstation.

Why streaming and not ``?POLL;``: gpsd only ships the satellite list in
the **SKY reports of a JSON watch**. Its ``?POLL;`` answer carries the
DOP values but never ``satellites`` / ``nSat`` / ``uSat`` — measured on
the Pi's gpsd 3.25, on a single connection, *after* streamed SKY reports
had shown ``nSat=15 uSat=9``. ``gpsd-py3`` (used until journal S51) only
ever polls, which is why ``details.satellites`` was structurally stuck at
0 and the ``searching`` state was unreachable.

State mapping (gpsd ``mode`` + satellites *seen*):

    =============  ===========
    mode           state
    =============  ===========
    2              fix_2d
    3              fix_3d
    <2, seen > 0   searching
    else           no_fix
    =============  ===========

The connection lives inside the loop, not in :meth:`start`, so a gpsd
that is down or restarts never takes the backend down with it: the
adapter publishes ``no_fix`` and keeps retrying every
:data:`RECONNECT_DELAY_S`. A silent stream is also a failure — the
receiver can be unplugged without gpsd saying anything — so
:data:`STALE_TIMEOUT_S` without a report clears the position rather than
freezing the state on the last fix. The **TPV expires on its own** by
the same deadline: SKY alone keeps the stream alive, so a receiver that
stops reporting positions while still reporting satellites would
otherwise leave the last fix frozen — and re-stamped as current on
every SKY.

Publishing is throttled: the enum is emitted as soon as it changes, but
detail updates (lat/lon/altitude/hdop/satellites) are limited to one
publish every :data:`DETAIL_THROTTLE_S` seconds when the enum hasn't
moved.

Logging is per *transition*, never per report: one line when the state
enum moves, and one warning per failure episode (re-armed on recovery).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import GpsFix
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)

GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947
# json=true is the whole point: the default watch (json=false) streams
# nothing and leaves us with ?POLL;, which has no satellite count.
WATCH_COMMAND = b'?WATCH={"enable":true,"json":true}\n'
STALE_TIMEOUT_S = 5.0
# Deliberately the same magnitude as STALE_TIMEOUT_S, but a distinct
# concern: that one bounds the silence of the *stream*, this one the
# age of the last *position*. SKY keeps the stream alive, so only this
# deadline can expire a fix that stopped being refreshed.
FIX_TIMEOUT_S = 5.0
RECONNECT_DELAY_S = 2.0
DETAIL_THROTTLE_S = 1.0


def mode_to_state(mode: int, satellites: int) -> str:
    """Classify a gpsd ``mode`` + satellites *seen* into the ``gps`` enum.

    ``satellites`` is the number of birds the antenna sees (``nSat``), not
    the number used in the solution (``uSat``): before a fix the used
    count is 0, so keying ``searching`` on it would never fire.
    """
    if mode == 2:
        return "fix_2d"
    if mode == 3:
        return "fix_3d"
    if satellites > 0:
        return "searching"
    return "no_fix"


def _sat_counts(sky: dict[str, Any]) -> tuple[int, int]:
    """Return ``(seen, used)`` from a gpsd SKY report.

    ``nSat`` / ``uSat`` exist since gpsd 3.20; older daemons only send the
    ``satellites`` array, so fall back to counting it.
    """
    seen = sky.get("nSat")
    used = sky.get("uSat")
    if seen is not None or used is not None:
        return int(seen or 0), int(used or 0)
    sats = sky.get("satellites") or []
    return len(sats), sum(1 for s in sats if s.get("used"))


class GpsdAdapter:
    """Consumes the gpsd JSON stream and publishes ``gps`` state on the bus."""

    def __init__(
        self, bus: StateBus, *, host: str = GPSD_HOST, port: int = GPSD_PORT
    ) -> None:
        self._bus = bus
        self._host = host
        self._port = port
        self._task: asyncio.Task[None] | None = None
        self._last_state: str | None = None
        self._last_detail_publish: datetime | None = None
        self._last_fix: GpsFix | None = None
        # Latest known content of each class. TPV carries the fix, SKY the
        # satellites and the DOPs; they arrive in separate messages, so both
        # are retained and combined on every publish. SKY accumulates
        # field-wise — see :meth:`_ingest`.
        self._tpv: dict[str, Any] = {}
        self._sky: dict[str, Any] = {}
        # Arrival time of the retained TPV, so it can expire without
        # waiting for the whole stream to go silent.
        self._tpv_at: datetime | None = None
        # One warning per failure episode, re-armed once a stream succeeds.
        self._error_logged: bool = False

    async def start(self) -> None:
        self._bus.publish(
            "gps",
            SubsystemState(state="no_fix", since=datetime.now(UTC)),
        )
        self._last_state = "no_fix"
        self._task = asyncio.create_task(self._loop(), name="gpsd-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._last_fix = None
        self._bus.publish(
            "gps",
            SubsystemState(state="off", since=datetime.now(UTC)),
        )

    def latest_fix(self) -> GpsFix | None:
        """Return the last live position, or ``None`` when there is no fix."""
        return self._last_fix

    async def _loop(self) -> None:
        while True:
            try:
                await self._stream_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Keep the adapter alive across gpsd restarts and refused
                # connections, and log the first failure of an episode so it
                # is diagnosable from journalctl — without repeating it.
                if not self._error_logged:
                    logger.warning("gpsd stream failed", exc_info=True)
                    self._error_logged = True
            self._forget()
            await asyncio.sleep(RECONNECT_DELAY_S)

    async def _stream_once(self) -> None:
        """Hold one watch session, ingesting reports until it breaks."""
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            writer.write(WATCH_COMMAND)
            await writer.drain()
            if self._error_logged:
                logger.info("gpsd stream recovered")
                self._error_logged = False
            while True:
                try:
                    line = await asyncio.wait_for(
                        reader.readline(), STALE_TIMEOUT_S
                    )
                except TimeoutError:
                    # gpsd is up but says nothing: receiver unplugged or
                    # daemon wedged. Drop the fix instead of serving a
                    # stale position to the orchestrator.
                    self._forget()
                    continue
                if not line:
                    return  # EOF: gpsd closed the socket
                self._ingest(line)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    def _ingest(self, line: bytes) -> None:
        try:
            report = json.loads(line)
        except ValueError:
            return  # not our business: gpsd only sends JSON lines
        cls = report.get("class")
        if cls == "TPV":
            self._tpv = report
            self._tpv_at = datetime.now(UTC)
        elif cls == "SKY":
            # gpsd alternates a full SKY with one reduced to the DOPs
            # (measured on 3.25: 24/14, then nothing, then 24/14...).
            # Merging keeps the counts instead of erasing them every other
            # report; a SKY that really sees nothing overwrites them with 0.
            self._sky = self._sky | report
        else:
            return  # VERSION / DEVICES / WATCH: acks, no state to derive
        self._publish()

    def _forget(self) -> None:
        """Drop everything we knew and republish (position included)."""
        self._tpv = {}
        self._sky = {}
        self._tpv_at = None
        self._publish()

    def _publish(self) -> None:
        now = datetime.now(UTC)
        tpv, sky = self._tpv, self._sky
        # gpsd emits SKY at 1 Hz whether or not there is a fix, so the
        # readline deadline never fires while satellites keep coming.
        # A TPV that stopped arriving must therefore expire on its own,
        # or ``latest_fix()`` would serve a frozen position — which the
        # orchestrator syncs to the mount and the wizard uses as the
        # observer position.
        fix_at = self._tpv_at
        if fix_at is not None and now - fix_at > timedelta(
            seconds=FIX_TIMEOUT_S
        ):
            fix_at = None
        mode = int(tpv.get("mode") or 0) if fix_at is not None else 0
        seen, used = _sat_counts(sky)
        state = mode_to_state(mode, seen)

        details: dict[str, Any] = {
            "satellites": used,
            "satellites_visible": seen,
        }
        lat, lon = tpv.get("lat"), tpv.get("lon")
        if mode >= 2 and lat is not None and lon is not None:
            details["lat"] = float(lat)
            details["lon"] = float(lon)
        if mode == 3:
            # ``alt`` is gpsd's deprecated alias of ``altMSL``.
            altitude = tpv.get("altMSL", tpv.get("alt"))
            if altitude is not None:
                details["altitude_m"] = float(altitude)
        hdop = sky.get("hdop")
        if hdop is not None:
            details["hdop"] = float(hdop)

        # Typed live position, refreshed on every report regardless of the
        # bus-publish throttle below — the two functional consumers
        # (orchestrator, alignment bridge) read this, not the bus details.
        if fix_at is not None and "lat" in details and "lon" in details:
            self._last_fix = GpsFix(
                lat=details["lat"],
                lon=details["lon"],
                timestamp=fix_at,
                is_3d=(mode == 3),
            )
        else:
            self._last_fix = None

        state_changed = state != self._last_state
        detail_ready = (
            self._last_detail_publish is None
            or now - self._last_detail_publish >= timedelta(seconds=DETAIL_THROTTLE_S)
        )
        if state_changed:
            logger.info(
                "gps state: %s -> %s (seen=%d used=%d)",
                self._last_state or "-",
                state,
                seen,
                used,
            )
        if state_changed or detail_ready:
            self._bus.publish(
                "gps",
                SubsystemState(state=state, details=details, since=now),
            )
            self._last_state = state
            self._last_detail_publish = now
