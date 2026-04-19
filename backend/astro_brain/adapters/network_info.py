"""Network info adapter — reads interface state from sysfs + userland tools.

Pi-native. Polls :data:`POLL_INTERVAL_S` seconds:

* ``/sys/class/net/<iface>/operstate`` → up / down;
* ``ip -4 -o addr show dev <iface>`` → current IPv4;
* ``iwgetid -r <iface>``             → associated SSID.

The enum is ``offline`` when the interface is down,
``hotspot`` when the SSID starts with :data:`HOTSPOT_SSID_PREFIX`
(the Pi is running its own access point), otherwise ``client``.
Publishing is throttled: the adapter only emits when
``(state, details)`` changes compared to the previous tick.
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState

NET_PATH = Path("/sys/class/net")
POLL_INTERVAL_S = 5.0
PRIMARY_INTERFACE = "wlan0"
HOTSPOT_SSID_PREFIX = "astro-brain"


def _interface_is_up(iface: str) -> bool:
    operstate = NET_PATH / iface / "operstate"
    if not operstate.exists():
        return False
    return operstate.read_text().strip() == "up"


def _iface_ip(iface: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "dev", iface], text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if "inet" in parts:
            i = parts.index("inet")
            return parts[i + 1].split("/")[0]
    return None


def _ssid(iface: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["iwgetid", "-r", iface], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.strip() or None


def _compute_network(iface: str) -> tuple[str, dict[str, Any]]:
    if not _interface_is_up(iface):
        return "offline", {"ssid": None, "ip": None}
    ssid = _ssid(iface)
    ip = _iface_ip(iface)
    if ssid and ssid.startswith(HOTSPOT_SSID_PREFIX):
        return "hotspot", {"ssid": ssid, "ip": ip}
    return "client", {"ssid": ssid, "ip": ip}


class NetworkInfoAdapter:
    """Polls network state and publishes on the bus when it changes."""

    def __init__(
        self, bus: StateBus, *, interface: str = PRIMARY_INTERFACE
    ) -> None:
        self._bus = bus
        self._iface = interface
        self._task: asyncio.Task[None] | None = None
        self._last: tuple[str, dict[str, Any]] | None = None

    async def start(self) -> None:
        self._publish_current()
        self._task = asyncio.create_task(self._loop(), name="network-info-loop")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def _publish_current(self) -> None:
        state, details = _compute_network(self._iface)
        current = (state, details)
        if self._last == current:
            return
        self._last = current
        self._bus.publish(
            "network",
            SubsystemState(
                state=state,
                details=dict(details),
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
                continue
