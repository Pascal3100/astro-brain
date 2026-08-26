"""Sonde « l'horloge système est-elle synchronisée sur le réseau ? ».

Couvre un défaut latent trouvé lors du retrait du module DroTek (cf. ADR
2026-08-26) : sans Internet, ``fake-hwclock`` restitue au boot l'heure du
dernier arrêt, et l'orchestrateur poussait cette heure vers la monture **sans
aucun contrôle**. Le déclenchement sur fix GPS ne protégeait pas de ça — le
GPS n'a jamais discipliné l'horloge, il n'était qu'un déclencheur.

Deux chemins, dans cet ordre :

1. ``systemd-timesyncd`` — le démon crée ``/run/systemd/timesync/synchronized``
   dès la première synchronisation réussie. Un simple ``stat`` : gratuit,
   appelable à chaque tick.
2. sinon (``chrony``, ``ntpd``…) — ``timedatectl show`` renvoie la propriété
   ``NTPSynchronized`` de systemd. C'est un sous-processus : le résultat est
   mis en cache :data:`_CACHE_TTL_S` secondes.

Toute lecture qui échoue vaut ``False`` : on refuse de pousser une heure
qu'on ne sait pas valider. Le coût d'un refus est une monture non synchronisée
(rattrapable) ; le coût d'un faux positif est un pointage faux sans le savoir.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

TIMESYNCD_FLAG = Path("/run/systemd/timesync/synchronized")

_CACHE_TTL_S = 60.0
_TIMEDATECTL_TIMEOUT_S = 2.0

_cache: tuple[float, bool] | None = None


def _timedatectl_synced() -> bool:
    """Interroge ``timedatectl``, résultat mis en cache (sous-processus)."""
    global _cache

    now = time.monotonic()
    if _cache is not None and (now - _cache[0]) < _CACHE_TTL_S:
        return _cache[1]

    try:
        completed = subprocess.run(
            ["timedatectl", "show", "--property=NTPSynchronized", "--value"],
            capture_output=True,
            text=True,
            timeout=_TIMEDATECTL_TIMEOUT_S,
            check=False,
        )
        synced = completed.returncode == 0 and completed.stdout.strip() == "yes"
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("clock_sync: timedatectl indisponible (%s)", exc)
        synced = False

    _cache = (now, synced)
    return synced


def reset_cache() -> None:
    """Vide le cache du chemin ``timedatectl`` (tests, ou après un boot)."""
    global _cache
    _cache = None


def is_clock_synced() -> bool:
    """``True`` si l'horloge système a été synchronisée sur une source réseau."""
    try:
        if TIMESYNCD_FLAG.parent.is_dir():
            return TIMESYNCD_FLAG.exists()
    except OSError as exc:
        logger.debug("clock_sync: /run/systemd/timesync illisible (%s)", exc)
        return False
    return _timedatectl_synced()
