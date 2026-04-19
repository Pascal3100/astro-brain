"""Protocol types for every service.

Routes and the orchestrator depend on these protocols, not on concrete
classes. The application wires either a ``Fake*`` (dev / tests) or a
real hardware adapter (on the Pi) at startup — without touching the
consumers.

Using :class:`typing.Protocol` gives us structural typing (PEP 544):
any class that implements the right methods satisfies the protocol
without inheriting from it.
"""

from __future__ import annotations

from typing import Literal, Protocol

Axis = Literal["alt", "az"]
Direction = Literal["+", "-"]


class MountService(Protocol):
    """Telescope mount driver."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None: ...
    async def stop_slew(self, axis: Axis | None) -> None: ...

    async def set_time(self, utc_iso: str) -> None: ...
    async def set_location(self, lat: float, lon: float) -> None: ...


class TrackingService(Protocol):
    """Sidereal tracking on/off control."""

    async def set_tracking(self, enabled: bool) -> None: ...


class GpsService(Protocol):
    """GPS receiver lifecycle."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class NetworkService(Protocol):
    """Network state watcher (client / hotspot / offline)."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class SystemInfoService(Protocol):
    """Host health watcher (CPU temp, load, uptime)."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
