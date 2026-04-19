"""Compute the overall system health color from per-subsystem states.

Rules (first match wins):

1. Any critical subsystem in a fatal state -> ``"red"``
2. Any subsystem in a transient state     -> ``"blue"``
3. Any subsystem in a degraded state      -> ``"orange"``
4. Otherwise                              -> ``"green"``

In v0.1 the only critical subsystem is ``mount``.
"""

from __future__ import annotations

from astro_brain.subsystems import SubsystemState

CRITICAL_SUBSYSTEMS: frozenset[str] = frozenset({"mount"})

FATAL_STATES: frozenset[str] = frozenset({"disconnected", "error"})
TRANSIENT_STATES: frozenset[str] = frozenset({"connecting", "searching"})
DEGRADED_STATES: frozenset[str] = frozenset(
    {"no_fix", "warning", "critical", "offline"}
)


def compute_overall(subsystems: dict[str, SubsystemState]) -> str:
    """Return the overall color for the given subsystem snapshot."""
    for name, s in subsystems.items():
        if name in CRITICAL_SUBSYSTEMS and s.state in FATAL_STATES:
            return "red"
    for s in subsystems.values():
        if s.state in TRANSIENT_STATES:
            return "blue"
    for s in subsystems.values():
        if s.state in DEGRADED_STATES:
            return "orange"
    return "green"
