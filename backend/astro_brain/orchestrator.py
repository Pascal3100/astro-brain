"""Boot orchestrator: pousse le site d'observation et l'heure à la monture.

Écoute la :class:`StateBus` et, dès que la monture rapporte ``ready``, appelle
:meth:`MountService.set_location` (si un site est connu) et
:meth:`MountService.set_time` (si l'horloge est fiable) une seule fois. Si la
monture quitte l'état ``ready``, l'orchestrateur se réarme pour que la
prochaine occurrence déclenche une nouvelle sync (edge-triggered).

Deux gardes, chacune indépendante :

* **position** — elle vient du provider de position (site d'observation
  persisté), plus d'un fix GPS. Pas de site connu ⇒ pas de ``set_location``.
* **heure** — elle a toujours été l'heure NTP du Pi, jamais celle du GPS. Elle
  n'est poussée que si :func:`is_clock_synced` le confirme : sans réseau,
  ``fake-hwclock`` restitue l'heure du dernier arrêt (cf. ADR 2026-08-26).

Tant qu'aucune des deux poussées n'a eu lieu, l'orchestrateur reste armé : une
horloge qui se synchronise après le boot déclenche la sync au prochain
événement de bus.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from astro_brain.adapters.clock_sync import is_clock_synced
from astro_brain.bus import StateBus, iter_state_snapshots
from astro_brain.services.interfaces import MountService
from astro_brain.subsystems import MountState, SubsystemState

logger = logging.getLogger(__name__)


class PositionProvider(Protocol):
    """Source de la position d'observation (site persisté)."""

    def position(self) -> tuple[float, float] | None: ...


class Orchestrator:
    """Watches the bus and syncs the mount the first time it reports ready."""

    def __init__(
        self,
        *,
        bus: StateBus,
        mount: MountService,
        position: PositionProvider,
        clock_synced: Callable[[], bool] = is_clock_synced,
    ) -> None:
        self._bus = bus
        self._mount = mount
        self._position = position
        self._clock_synced = clock_synced
        self._synced = False

    async def run(self) -> None:
        """Subscribe to the bus and react to every state change until cancelled."""
        async for subsystems in iter_state_snapshots(self._bus):
            await self._maybe_sync(subsystems)

    async def _maybe_sync(self, subsystems: dict[str, SubsystemState]) -> None:
        mount_s = subsystems.get("mount")
        if mount_s is None:
            return

        if mount_s.state != MountState.READY.value:
            if self._synced:
                logger.info("orchestrator: monture non prête, réarmé")
            self._synced = False
            return
        if self._synced:
            return

        pushed = False

        pos = self._position.position()
        if pos is None:
            logger.info(
                "orchestrator: aucun site d'observation connu — position NON poussée"
            )
        else:
            lat, lon = pos
            logger.info("orchestrator: syncing location (lat=%s, lon=%s)", lat, lon)
            await self._mount.set_location(lat, lon)
            pushed = True

        if self._clock_synced():
            now_iso = datetime.now(UTC).isoformat()
            logger.info("orchestrator: syncing time (time=%s)", now_iso)
            await self._mount.set_time(now_iso)
            pushed = True
        else:
            logger.warning(
                "orchestrator: horloge non synchronisée — heure NON poussée "
                "vers la monture"
            )

        # Rester armé tant que rien n'est passé : l'horloge peut se
        # synchroniser, ou un site être réglé, après le passage en ready.
        self._synced = pushed
