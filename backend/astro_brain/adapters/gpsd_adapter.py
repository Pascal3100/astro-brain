"""Gpsd adapter for the DroTek GPS module.

Requires the ``gpsd-py3`` extra (``uv sync --extra hardware``). The
``gpsd`` module is imported *lazily* inside :meth:`start` and
:meth:`_loop` so this module remains importable on a workstation that
lacks the hardware extras — only :meth:`start` will fail there.

State mapping (gpsd ``mode``):

    ======  ===========
    mode    state
    ======  ===========
    2       fix_2d
    3       fix_3d
    <2, sats > 0   searching
    else    no_fix
    ======  ===========

Publishing is throttled: the enum is emitted as soon as it changes, but
detail updates (lat/lon/altitude/hdop) are limited to one publish every
:data:`DETAIL_THROTTLE_S` seconds when the enum hasn't moved.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.5
DETAIL_THROTTLE_S = 1.0


def mode_to_state(mode: int, satellites: int) -> str:
    """Classify a gpsd ``mode`` + satellite count into the ``gps`` state enum."""
    if mode == 2:
        return "fix_2d"
    if mode == 3:
        return "fix_3d"
    if satellites > 0:
        return "searching"
    return "no_fix"


class GpsdAdapter:
    """Consumes the gpsd stream and publishes ``gps`` state on the bus."""

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._task: asyncio.Task[None] | None = None
        self._last_state: str | None = None
        self._last_detail_publish: datetime | None = None
        # gpsd-py3.get_current() returns the latest packet (usually TPV, with
        # sats_valid=0); only SKY packets carry the real count. Keep the last
        # non-zero value sticky so ``details.satellites`` doesn't flap to 0.
        self._last_sats: int = 0

    async def start(self) -> None:
        import gpsd  # type: ignore[import-not-found]

        await asyncio.to_thread(gpsd.connect)
        self._bus.publish(
            "gps",
            SubsystemState(state="no_fix", since=datetime.now(timezone.utc)),
        )
        self._task = asyncio.create_task(self._loop(), name="gpsd-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._bus.publish(
            "gps",
            SubsystemState(state="off", since=datetime.now(timezone.utc)),
        )

    async def _loop(self) -> None:
        import gpsd  # type: ignore[import-not-found]

        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_S)
                packet = await asyncio.to_thread(gpsd.get_current)
                mode = int(getattr(packet, "mode", 0) or 0)
                sats_now = int(getattr(packet, "sats_valid", 0) or 0)
                if sats_now > 0:
                    self._last_sats = sats_now
                sats = self._last_sats
                state = mode_to_state(mode, sats)
                details: dict[str, Any] = {"satellites": sats}

                if mode >= 2:
                    with contextlib.suppress(Exception):
                        lat, lon = packet.position()
                        details["lat"] = lat
                        details["lon"] = lon
                if mode == 3:
                    with contextlib.suppress(Exception):
                        details["altitude_m"] = packet.altitude()
                hdop = getattr(packet, "hdop", None)
                if hdop is not None:
                    details["hdop"] = float(hdop)

                now = datetime.now(timezone.utc)
                state_changed = state != self._last_state
                detail_ready = (
                    self._last_detail_publish is None
                    or now - self._last_detail_publish
                    >= timedelta(seconds=DETAIL_THROTTLE_S)
                )
                if state_changed or detail_ready:
                    self._bus.publish(
                        "gps",
                        SubsystemState(state=state, details=details, since=now),
                    )
                    self._last_state = state
                    self._last_detail_publish = now
            except asyncio.CancelledError:
                return
            except Exception:
                # Keep the loop alive across transient gpsd errors, but log
                # them so silent failures can be diagnosed from journalctl.
                logger.warning("gpsd poll failed", exc_info=True)
                continue
