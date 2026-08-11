"""Boot orchestrator: syncs the mount with GPS + time when both are ready.

Listens on the :class:`StateBus` and, when the mount reports ``ready`` AND
the GPS reports a fix (``fix_2d`` or ``fix_3d``), calls
:meth:`MountService.set_time` + :meth:`MountService.set_location` exactly
once. If either dependency transitions away from the ready state, the
orchestrator rearms so the next co-occurrence triggers a fresh sync
(edge-triggered, not level-triggered).

The sync *trigger* still watches the bus's ``gps`` health state (a
legitimate health event), but the lat/lon it applies come from the typed
:class:`~astro_brain.services.interfaces.GpsSource` rather than the bus
``details`` dict — the bus stays dedicated to health/display.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import GpsSource, MountService
from astro_brain.subsystems import GpsState, MountState, SubsystemState

logger = logging.getLogger(__name__)

GPS_FIX_STATES = frozenset({GpsState.FIX_2D.value, GpsState.FIX_3D.value})


class Orchestrator:
    """Watches the bus and syncs the mount on the first mount+gps co-occurrence."""

    def __init__(self, *, bus: StateBus, mount: MountService, gps: GpsSource) -> None:
        self._bus = bus
        self._mount = mount
        self._gps = gps
        self._synced = False

    async def run(self) -> None:
        """Subscribe to the bus and react to every state change until cancelled."""
        async for _event in self._bus.subscribe():
            full = self._bus.get_full_state()
            await self._maybe_sync(full.subsystems)

    async def _maybe_sync(self, subsystems: dict[str, SubsystemState]) -> None:
        mount_s = subsystems.get("mount")
        gps_s = subsystems.get("gps")
        if mount_s is None or gps_s is None:
            return

        conditions_met = (
            mount_s.state == MountState.READY.value
            and gps_s.state in GPS_FIX_STATES
        )
        if not conditions_met:
            if self._synced:
                logger.info("orchestrator: sync conditions lost, rearmed")
            self._synced = False
            return
        if self._synced:
            return

        fix = self._gps.latest_fix()
        if fix is None:
            return
        lat, lon = fix.lat, fix.lon

        now_iso = datetime.now(UTC).isoformat()
        logger.info(
            "orchestrator: syncing mount (time=%s, lat=%s, lon=%s)",
            now_iso,
            lat,
            lon,
        )
        await self._mount.set_time(now_iso)
        await self._mount.set_location(lat, lon)
        self._synced = True
