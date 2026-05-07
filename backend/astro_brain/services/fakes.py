"""Fake service implementations used by tests and local dev.

They are deterministic, synchronous-fast, and programmable — they never
touch hardware. Use them from tests and when running the backend without
the ``[hardware]`` extras.

Fake I2C adapters for the calibration service are defined at the bottom of
this module. They are not exported publicly (leading underscore); access
them via :func:`make_fake_calibration_adapters`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(UTC)


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
                details={"active_slews": [dict(s) for s in self._active_slews]},
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
                    details={"active_slews": [dict(s) for s in self._active_slews]},
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

    # --- cordwrap (in-memory toggles) ------------------------------------

    _cordwrap_enabled: bool = False
    _cordwrap_position: str = "N"

    async def cordwrap_get_enabled(self) -> bool:
        return self._cordwrap_enabled

    async def cordwrap_set_enabled(self, enabled: bool) -> None:
        self._cordwrap_enabled = bool(enabled)

    async def cordwrap_get_position(self) -> str:
        return self._cordwrap_position

    async def cordwrap_set_position(self, position: str) -> None:
        if position not in {"N", "E", "S", "W"}:
            raise ValueError(f"invalid cordwrap position: {position!r}")
        self._cordwrap_position = position

    # --- backlash (in-memory 4-value table) -----------------------------

    _backlash_table: dict[tuple[str, str], int] = {  # noqa: RUF012
        ("alt", "+"): 0,
        ("alt", "-"): 0,
        ("az", "+"): 0,
        ("az", "-"): 0,
    }

    async def get_backlash(self, axis: Axis, direction: Direction) -> int:
        return self._backlash_table[(axis, direction)]

    async def set_backlash(
        self, axis: Axis, direction: Direction, value: int
    ) -> None:
        if not 0 <= int(value) <= 99:
            raise ValueError(f"backlash value out of range: {value}")
        self._backlash_table[(axis, direction)] = int(value)


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

    def current_snapshot(self) -> dict[str, str | None]:
        """Return the constructor-injected ``{"ip": ..., "ssid": ...}``."""
        return {"ip": self._ip, "ssid": self._ssid}

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

    def current_snapshot(self) -> dict[str, int | None]:
        """Return the constructor-injected ``{"uptime_s": ...}``."""
        return {"uptime_s": self._uptime_s}

    async def stop(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Fake I2C adapters for CalibrationServiceImpl (dev / tests)
# ---------------------------------------------------------------------------


class _FakeAdxl345:
    """Infinite-sequence ADXL345 fake for calibration tests and local dev."""

    def __init__(
        self, samples: list[tuple[float, float, float]] | None = None
    ) -> None:
        self._samples = list(samples) if samples else [(0.0, 0.0, 1.0)] * 1_000_000
        self._idx = 0

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def read_raw_g(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


class _FakeLis3mdl:
    """Infinite-sequence LIS3MDL fake for calibration tests and local dev."""

    def __init__(
        self, samples: list[tuple[float, float, float]] | None = None
    ) -> None:
        self._samples = (
            list(samples) if samples else [(50.0, 0.0, 30.0)] * 1_000_000
        )
        self._idx = 0

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def read_raw(self) -> tuple[float, float, float]:
        s = self._samples[min(self._idx, len(self._samples) - 1)]
        self._idx += 1
        return s


def make_fake_calibration_adapters() -> tuple[_FakeAdxl345, _FakeAdxl345, _FakeLis3mdl]:
    """Return ``(adxl_mount, adxl_tube, lis3mdl)`` fakes for local dev."""
    return _FakeAdxl345(), _FakeAdxl345(), _FakeLis3mdl()
