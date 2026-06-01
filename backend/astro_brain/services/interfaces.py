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

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
from astro_brain.models.calibration import CalibrationProgress, CalibrationStatus

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

    async def sync_radec(self, ra_deg: float, dec_deg: float) -> None:
        """Push a sync point to the mount's native alignment model.

        Implementations must use the INDI standard pattern
        ``ON_COORD_SET=SYNC`` then ``EQUATORIAL_EOD_COORD`` so the
        Celestron AUX driver feeds its built-in 3-star model.
        ``ra_deg`` is degrees [0, 360); the INDI element is hours
        (``ra_deg / 15``). ``dec_deg`` is degrees [-90, 90].
        """
        ...

    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        """Pointe la monture sur (ra, dec) et enchaîne le tracking sidéral.

        Pattern INDI ``ON_COORD_SET=TRACK`` puis ``EQUATORIAL_EOD_COORD``
        (RA en heures, DEC en degrés, JNow). Publie l'état ``moving`` avec
        ``details.goto_in_progress = True`` ; l'arrivée (propriété passée à
        ``Ok``/``Idle``) repasse en ``ready``.
        """
        ...

    async def cordwrap_get_enabled(self) -> bool: ...
    async def cordwrap_set_enabled(self, enabled: bool) -> None: ...
    async def cordwrap_get_position(self) -> str: ...
    async def cordwrap_set_position(self, position: str) -> None: ...

    async def get_backlash(self, axis: Axis, direction: Direction) -> int: ...
    async def set_backlash(
        self, axis: Axis, direction: Direction, value: int
    ) -> None: ...


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
    def current_snapshot(self) -> dict[str, str | None]: ...


class SystemInfoService(Protocol):
    """Host health watcher (CPU temp, load, uptime)."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def current_snapshot(self) -> dict[str, int | None]: ...


class ConflictError(Exception):
    """A calibration session is already active for another sensor."""


class CalibrationService(Protocol):
    """Orchestrates per-sensor calibration sessions.

    A single session is active at a time across all sensors. Trying to
    ``start`` a second session raises :class:`ConflictError` until the
    current one is ``finalize``'d or ``abort``'ed.

    SSE clients disconnecting mid-stream do **not** terminate the session —
    explicit ``abort`` is required. The router stops yielding SSE events
    when the client disconnects, but the sampling loop on the backend
    continues until ``abort`` or ``finalize`` is called.
    """

    async def start(self, sensor_id: str) -> str: ...
    async def progress(self, session_id: str) -> AsyncIterator[CalibrationProgress]: ...
    async def finalize(self, session_id: str) -> CalibrationStatus: ...
    async def abort(self, session_id: str) -> None: ...
    async def current_session(self) -> tuple[str, str] | None: ...


class AlignmentService(Protocol):
    """Wizard d'alignement 3 étoiles (session unique en RAM)."""

    async def start(self) -> AlignmentSession: ...
    async def swap(self, idx: int, new_star: Star) -> AlignmentSession: ...
    async def record(self, idx: int) -> AlignmentSession: ...
    async def restart_star(self, idx: int) -> AlignmentSession: ...
    async def finalize(self) -> AlignmentModel: ...
    async def cancel(self) -> None: ...
    def session(self) -> AlignmentSession | None: ...

    @property
    def is_aligned(self) -> bool: ...
    def invalidate(self) -> None: ...
