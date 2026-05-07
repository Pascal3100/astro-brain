"""System info adapter — reads CPU temperature and load from sysfs/procfs.

Designed for a Raspberry Pi running Pi OS. On boot and every
:data:`POLL_INTERVAL_S` seconds, the adapter reads::

    /sys/class/thermal/thermal_zone0/temp  (milli-degrees Celsius)
    /proc/uptime                           (seconds since boot, float)
    /proc/loadavg                          (1-minute load avg, first field)

It then publishes a ``"system"`` :class:`~astro_brain.subsystems.SubsystemState`
on the :class:`~astro_brain.bus.StateBus`. The state enum follows the
thresholds defined below (``ok`` → ``warning`` → ``critical``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState

THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
UPTIME_PATH = Path("/proc/uptime")
LOADAVG_PATH = Path("/proc/loadavg")

POLL_INTERVAL_S = 5.0
WARN_TEMP_C = 70.0
CRIT_TEMP_C = 80.0
WARN_LOAD = 1.5


def _read_temp_c() -> float:
    return int(THERMAL_PATH.read_text().strip()) / 1000.0


def _read_uptime_s() -> int:
    return int(float(UPTIME_PATH.read_text().split()[0]))


def _read_loadavg_1min() -> float:
    return float(LOADAVG_PATH.read_text().split()[0])


def compute_state(cpu_temp_c: float, cpu_load: float) -> str:
    """Classify the current CPU metrics into the ``system`` state enum."""
    if cpu_temp_c >= CRIT_TEMP_C:
        return "critical"
    if cpu_temp_c >= WARN_TEMP_C or cpu_load >= WARN_LOAD:
        return "warning"
    return "ok"


class SystemInfoAdapter:
    """Polls sysfs/procfs and publishes a ``system`` state on each tick."""

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._task: asyncio.Task[None] | None = None
        self._last_details: dict[str, Any] | None = None

    async def start(self) -> None:
        self._publish_current()
        self._task = asyncio.create_task(self._loop(), name="system-info-loop")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def current_snapshot(self) -> dict[str, int | None]:
        """Return the last known ``{"uptime_s": ...}`` without I/O.

        Returns ``{"uptime_s": None}`` when :meth:`start` has not yet been
        called (no data in cache).
        """
        if self._last_details is None:
            return {"uptime_s": None}
        return {"uptime_s": self._last_details.get("uptime_s")}

    def _publish_current(self) -> None:
        temp = _read_temp_c()
        load = _read_loadavg_1min()
        uptime = _read_uptime_s()
        details: dict[str, Any] = {
            "cpu_temp_c": temp,
            "cpu_load": load,
            "uptime_s": uptime,
        }
        self._last_details = details
        self._bus.publish(
            "system",
            SubsystemState(
                state=compute_state(temp, load),
                details=details,
                since=datetime.now(timezone.utc),
            ),
        )

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_S)
                self._publish_current()
            except asyncio.CancelledError:
                return
            except OSError:
                # transient sysfs/procfs read failure — keep the loop alive
                continue
