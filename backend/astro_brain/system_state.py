"""Composite system state: overall roll-up, per-subsystem state, monotonic seq."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from astro_brain.subsystems import SubsystemState


@dataclass(frozen=True)
class SystemState:
    """Full snapshot of the system broadcast to clients.

    Attributes:
        overall: Roll-up status — ``"green"``, ``"blue"``, ``"orange"`` or ``"red"``.
        subsystems: Per-subsystem state keyed by subsystem name.
        seq: Monotonic sequence number, incremented on every state change.
        ts: Timestamp of this snapshot.
    """

    overall: str
    subsystems: dict[str, SubsystemState]
    seq: int
    ts: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the snapshot."""
        return {
            "overall": self.overall,
            "subsystems": {
                name: s.to_dict() for name, s in self.subsystems.items()
            },
            "seq": self.seq,
            "ts": self.ts.isoformat(),
        }
