"""Boot orchestrator: syncs the mount with GPS + time when both are ready.

Listens on the :class:`StateBus` and, when the mount reports ``ready`` AND
the GPS reports a fix (``fix_2d`` or ``fix_3d``), calls
:meth:`MountService.set_time` + :meth:`MountService.set_location` exactly
once. If either dependency transitions away from the ready state, the
orchestrator rearms so the next co-occurrence triggers a fresh sync
(edge-triggered, not level-triggered).
"""

from __future__ import annotations

from datetime import datetime, timezone

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import MountService
from astro_brain.subsystems import SubsystemState

GPS_FIX_STATES = frozenset({"fix_2d", "fix_3d"})


class Orchestrator:
    """Watches the bus and syncs the mount on the first mount+gps co-occurrence."""

    def __init__(self, *, bus: StateBus, mount: MountService) -> None:
        self._bus = bus
        self._mount = mount
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
            mount_s.state == "ready" and gps_s.state in GPS_FIX_STATES
        )
        if not conditions_met:
            self._synced = False
            return
        if self._synced:
            return

        lat = gps_s.details.get("lat")
        lon = gps_s.details.get("lon")
        if lat is None or lon is None:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        await self._mount.set_time(now_iso)
        await self._mount.set_location(lat, lon)
        self._synced = True
