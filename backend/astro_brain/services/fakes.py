"""Fake service implementations used by tests and local dev.

They are deterministic, synchronous-fast, and programmable — they never
touch hardware. Use them from tests and when running the backend without
the ``[hardware]`` extras.

The fake I2C adapter for the calibration service is defined at the bottom
of this module. It is not exported publicly (leading underscore); access
it via :func:`make_fake_calibration_adapters`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction, GpsFix
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(UTC)


class FakeMount:
    """In-memory mount that publishes ``mount`` state on the bus."""

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._active_slews: list[dict[str, Any]] = []
        self.sync_calls: list[tuple[float, float]] = []
        self.goto_calls: list[tuple[float, float, str | None]] = []
        self.reconnect_calls: int = 0
        self.reconnect_requests: int = 0

    async def start(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"firmware_version": "fake-1.0"},
                since=_now(),
            ),
        )

    async def reconnect(self) -> None:
        self.reconnect_calls += 1
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"firmware_version": "fake-1.0"},
                since=_now(),
            ),
        )

    def request_reconnect(self) -> None:
        self.reconnect_requests += 1

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

    # --- sync (alignment model fed via INDI ON_COORD_SET=SYNC) -----------

    async def sync_radec(self, ra_deg: float, dec_deg: float) -> None:
        self.sync_calls.append((float(ra_deg), float(dec_deg)))

    # --- goto (slew vers coordonnées + tracking sidéral natif) -----------

    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        self.goto_calls.append((float(ra_deg), float(dec_deg), target_name))
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "goto_in_progress": True,
                    "goto": {
                        "target_name": target_name,
                        "ra_deg": float(ra_deg),
                        "dec_deg": float(dec_deg),
                    },
                },
                since=_now(),
            ),
        )

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

    def latest_fix(self) -> GpsFix | None:
        """Return the constructor-injected fix, honoring ``initial_state``."""
        if self._initial_state not in ("fix_2d", "fix_3d"):
            return None
        return GpsFix(
            lat=self._details["lat"],
            lon=self._details["lon"],
            timestamp=_now(),
            is_3d=self._initial_state == "fix_3d",
        )


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
# Fake I2C adapter for CalibrationServiceImpl (dev / tests)
# ---------------------------------------------------------------------------


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


def make_fake_calibration_adapters() -> _FakeLis3mdl:
    """Return the LIS3MDL fake for local dev."""
    return _FakeLis3mdl()
