"""Invalide le flag is_aligned quand la monture perd son modèle natif.

Le modèle 3-étoiles vit dans le driver INDI (en mémoire). Toute reconnexion
(transition mount → disconnected/connecting) signifie sa perte : on
remet ``is_aligned`` à faux. Edge-triggered : ne ré-invalide qu'après être
repassé par ``ready``.

Le state transitoire ``error`` (publié à chaque échec de commande INDI
récupérable, ex. sync_radec/goto_radec raté) n'invalide PAS l'alignement :
le driver ne se déconnecte pas, le modèle natif est préservé. Le latch
``_was_ready`` survit aux états transitoires non-perdants (ex. ``moving``,
``error``) jusqu'à une vraie reconnexion (``disconnected`` ou ``connecting``).

Branché sur le StateBus comme l'Orchestrator (une tâche de fond qui consomme
les events et appelle :meth:`on_mount_state`).
"""
from __future__ import annotations

import logging
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.subsystems import MountState, SubsystemState

logger = logging.getLogger(__name__)

_LOST_STATES = frozenset(
    {MountState.DISCONNECTED.value, MountState.CONNECTING.value}
)


class AlignmentInvalidator:
    """Clears is_aligned on mount reconnection (edge-triggered)."""

    def __init__(self, *, alignment: Any, bus: StateBus | None = None) -> None:
        self._alignment = alignment
        self._bus = bus
        self._was_ready = False

    def on_mount_state(self, state: str) -> None:
        if state == MountState.READY.value:
            self._was_ready = True
            return
        if state in _LOST_STATES and self._was_ready:
            logger.info("alignment: mount reconnection detected, invalidating model")
            self._alignment.invalidate()
            self._was_ready = False
            if self._bus is not None:
                self._bus.publish(
                    "alignment",
                    SubsystemState(state="idle", details={"is_aligned": False}),
                )

    async def run(self) -> None:
        """Consume bus events and react to mount state changes until cancelled."""
        if self._bus is None:
            return
        async for _event in self._bus.subscribe():
            mount = self._bus.get_full_state().subsystems.get("mount")
            if mount is not None:
                self.on_mount_state(mount.state)
