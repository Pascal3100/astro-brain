"""Fake service implementations used by tests and local dev.

They are deterministic, synchronous-fast, and programmable — they never
touch hardware. Use them from tests and when running the backend without
the ``[hardware]`` extras.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeMount:
    """In-memory mount that publishes ``mount`` state on the bus."""

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._active_slews: list[dict[str, Any]] = []

    async def start(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"firmware_version": "fake-1.0"},
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(state="disconnected", since=_now()),
        )

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        # replace any existing slew on the same axis
        self._active_slews = [s for s in self._active_slews if s["axis"] != axis]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={"active_slews": list(self._active_slews)},
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        if axis is None:
            self._active_slews = []
        else:
            self._active_slews = [
                s for s in self._active_slews if s["axis"] != axis
            ]
        if self._active_slews:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="moving",
                    details={"active_slews": list(self._active_slews)},
                    since=_now(),
                ),
            )
        else:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": "fake-1.0"},
                    since=_now(),
                ),
            )

    async def set_time(self, utc_iso: str) -> None:
        # fake mount does not persist time; just accept the call
        return None

    async def set_location(self, lat: float, lon: float) -> None:
        return None


class FakeTracking:
    """Sidereal tracking toggle published on the bus."""

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._bus.publish("tracking", SubsystemState(state="off", since=_now()))

    async def set_tracking(self, enabled: bool) -> None:
        value = "sidereal" if enabled else "off"
        self._bus.publish("tracking", SubsystemState(state=value, since=_now()))


class FakeGps:
    """Programmable GPS — publishes a synthetic fix on :meth:`start`."""

    def __init__(
        self,
        bus: StateBus,
        *,
        initial_state: str = "fix_3d",
        lat: float = 48.8566,
        lon: float = 2.3522,
        altitude_m: float = 45.0,
        sats: int = 8,
        hdop: float = 0.9,
    ) -> None:
        self._bus = bus
        self._initial_state = initial_state
        self._details: dict[str, Any] = {
            "lat": lat,
            "lon": lon,
            "altitude_m": altitude_m,
            "satellites": sats,
            "hdop": hdop,
        }

    async def start(self) -> None:
        self._bus.publish(
            "gps",
            SubsystemState(
                state=self._initial_state,
                details=dict(self._details),
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish("gps", SubsystemState(state="off", since=_now()))


class FakeNetwork:
    """Static network info published on :meth:`start`."""

    def __init__(
        self,
        bus: StateBus,
        *,
        state: str = "client",
        ssid: str = "fake-wifi",
        ip: str = "192.168.1.10",
    ) -> None:
        self._bus = bus
        self._state = state
        self._ssid = ssid
        self._ip = ip

    async def start(self) -> None:
        self._bus.publish(
            "network",
            SubsystemState(
                state=self._state,
                details={"ssid": self._ssid, "ip": self._ip},
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish(
            "network",
            SubsystemState(state="offline", since=_now()),
        )


class FakeSystemInfo:
    """System health fake — derives state from CPU temp / load thresholds."""

    WARN_TEMP = 70.0
    CRIT_TEMP = 80.0
    WARN_LOAD = 1.5

    def __init__(
        self,
        bus: StateBus,
        *,
        cpu_temp_c: float = 55.0,
        cpu_load: float = 0.4,
        uptime_s: int = 120,
    ) -> None:
        self._bus = bus
        self._cpu_temp_c = cpu_temp_c
        self._cpu_load = cpu_load
        self._uptime_s = uptime_s

    async def start(self) -> None:
        if self._cpu_temp_c >= self.CRIT_TEMP:
            state = "critical"
        elif (
            self._cpu_temp_c >= self.WARN_TEMP
            or self._cpu_load >= self.WARN_LOAD
        ):
            state = "warning"
        else:
            state = "ok"
        self._bus.publish(
            "system",
            SubsystemState(
                state=state,
                details={
                    "cpu_temp_c": self._cpu_temp_c,
                    "cpu_load": self._cpu_load,
                    "uptime_s": self._uptime_s,
                },
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        return None
