"""Compute the overall system health color from per-subsystem states.

Rules (first match wins):

1. Any critical subsystem in a fatal state -> ``"red"``
2. Any subsystem in a transient state     -> ``"blue"``
3. Any subsystem in a degraded state      -> ``"orange"``
4. Otherwise                              -> ``"green"``

In v0.1 the only critical subsystem is ``mount``.
"""

from __future__ import annotations

from astro_brain.subsystems import (
    GpsState,
    MountState,
    NetworkState,
    SubsystemState,
    SystemInfoState,
)

CRITICAL_SUBSYSTEMS: frozenset[str] = frozenset({"mount"})

# Sets are derived from the enums so a rename in ``subsystems.py`` breaks
# the aggregator at import time rather than causing silent misclassification.
FATAL_STATES: frozenset[str] = frozenset(
    {MountState.DISCONNECTED.value, MountState.ERROR.value}
)
TRANSIENT_STATES: frozenset[str] = frozenset(
    {MountState.CONNECTING.value, GpsState.SEARCHING.value}
)
DEGRADED_STATES: frozenset[str] = frozenset(
    {
        GpsState.NO_FIX.value,
        GpsState.OFF.value,
        SystemInfoState.WARNING.value,
        SystemInfoState.CRITICAL.value,
        NetworkState.OFFLINE.value,
    }
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
