"""State enums and the generic ``SubsystemState`` dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MountState(StrEnum):
    """Telescope mount lifecycle state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    MOVING = "moving"
    ERROR = "error"


class TrackingState(StrEnum):
    """Sidereal tracking state."""

    OFF = "off"
    SIDEREAL = "sidereal"


class NetworkState(StrEnum):
    """Network mode of the Pi."""

    OFFLINE = "offline"
    CLIENT = "client"
    HOTSPOT = "hotspot"


class SystemInfoState(StrEnum):
    """Host health roll-up (CPU temp, load, etc.)."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SubsystemState:
    """Generic state snapshot for any subsystem.

    Attributes:
        state: String value of the subsystem-specific enum (e.g. ``"ready"``).
        details: Free-form context (lat/lon, firmware version, CPU temp...).
        since: Timestamp of the last state change.
        message: Optional human-readable error or info string.
    """

    state: str
    details: dict[str, Any] = field(default_factory=dict)
    since: datetime | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the state."""
        return {
            "state": self.state,
            "details": dict(self.details),
            "since": self.since.isoformat() if self.since is not None else None,
            "message": self.message,
        }
