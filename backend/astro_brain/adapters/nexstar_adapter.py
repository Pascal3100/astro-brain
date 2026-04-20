"""NexStar mount adapter for the Celestron HC port.

Wraps ``nexstarpy`` (hardware extra: ``uv sync --extra hardware``). The
``nexstarpy`` module is imported *lazily* inside :meth:`start` so this
module stays importable on a workstation without the hardware deps — only
:meth:`start` will fail there.

The same adapter also serves as the :class:`TrackingService` on the Pi:
tracking on/off is a mount-level command, not an independent subsystem.

The ``set_tracking_mode`` NexStar constant may vary across firmware
versions (commonly ``1`` sidereal / ``2`` lunar / ``3`` solar). Verify on
real hardware (see Task 17) and adjust :data:`TRACKING_MODE_SIDEREAL` if
needed.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState

SERIAL_DEVICE_ENV = "ASTRO_BRAIN_SERIAL_DEVICE"
SERIAL_DEVICE_DEFAULT = "/dev/ttyUSB0"
WATCHDOG_INTERVAL_S = 2.0
TRACKING_MODE_SIDEREAL = 1
TRACKING_MODE_OFF = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_device() -> str:
    """Resolve the serial device from the environment, or fall back."""
    return os.environ.get(SERIAL_DEVICE_ENV, SERIAL_DEVICE_DEFAULT)


class NexStarMountAdapter:
    """Drives a Celestron NexStar mount and publishes ``mount`` state."""

    def __init__(self, bus: StateBus, *, device: str | None = None) -> None:
        self._bus = bus
        self._device = device if device is not None else _default_device()
        self._client: Any = None
        self._active_slews: list[dict[str, Any]] = []
        self._watchdog_task: asyncio.Task[None] | None = None
        self._firmware_version: str | None = None

    async def start(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(state="connecting", since=_now()),
        )
        try:
            import nexstarpy  # type: ignore[import-not-found]

            self._client = nexstarpy.NexStar(self._device)
            self._firmware_version = str(self._client.get_version())
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": self._firmware_version},
                    since=_now(),
                ),
            )
            # This adapter is also wired as the tracking service — seed the
            # ``tracking`` subsystem with an initial "off" state so it shows
            # up in /state before any /tracking call has been made.
            self._bus.publish(
                "tracking",
                SubsystemState(state="off", since=_now()),
            )
            self._watchdog_task = asyncio.create_task(
                self._watchdog(), name="mount-watchdog"
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def stop(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except (asyncio.CancelledError, Exception):
                pass
            self._watchdog_task = None
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass
        self._client = None
        self._bus.publish(
            "mount",
            SubsystemState(state="disconnected", since=_now()),
        )

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        if self._client is None:
            return
        self._active_slews = [
            s for s in self._active_slews if s["axis"] != axis
        ]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )
        try:
            self._client.slew_fixed(axis, direction, rate)
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "firmware_version": self._firmware_version,
                    "active_slews": list(self._active_slews),
                },
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        if self._client is None:
            return
        try:
            if axis is None:
                for a in ("alt", "az"):
                    self._client.stop_slew(a)
                self._active_slews = []
            else:
                self._client.stop_slew(axis)
                self._active_slews = [
                    s for s in self._active_slews if s["axis"] != axis
                ]
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return

        if self._active_slews:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="moving",
                    details={
                        "firmware_version": self._firmware_version,
                        "active_slews": list(self._active_slews),
                    },
                    since=_now(),
                ),
            )
        else:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": self._firmware_version},
                    since=_now(),
                ),
            )

    async def set_time(self, utc_iso: str) -> None:
        if self._client is None:
            return
        try:
            dt = datetime.fromisoformat(utc_iso)
            self._client.set_time(
                (
                    dt.year,
                    dt.month,
                    dt.day,
                    dt.hour,
                    dt.minute,
                    dt.second,
                    0,  # UTC offset hours
                    0,  # DST flag
                )
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def set_location(self, lat: float, lon: float) -> None:
        if self._client is None:
            return
        try:
            self._client.set_location(lat, lon)
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def set_tracking(self, enabled: bool) -> None:
        if self._client is None:
            return
        try:
            mode = TRACKING_MODE_SIDEREAL if enabled else TRACKING_MODE_OFF
            self._client.set_tracking_mode(mode)
            value = "sidereal" if enabled else "off"
            self._bus.publish(
                "tracking",
                SubsystemState(state=value, since=_now()),
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def _watchdog(self) -> None:
        while True:
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL_S)
                if self._client is None:
                    return
                self._client.get_version()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                # Watchdog exits permanently on the first failure — the
                # adapter does NOT auto-reconnect in v0.1. The operator must
                # restart the service to recover. This is documented in
                # backend/deploy/INTEGRATION_CHECKLIST.md (section 3).
                self._bus.publish(
                    "mount",
                    SubsystemState(
                        state="error",
                        message=(
                            f"mount watchdog failed: {exc}. "
                            "Restart astro-brain.service to reconnect."
                        ),
                        since=_now(),
                    ),
                )
                return
