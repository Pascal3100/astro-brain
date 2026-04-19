"""Module-level dependency registry.

Routes read their collaborators through the callables exposed here; the
application binds each one to a fake or a real implementation at startup
(see :mod:`astro_brain.app`). Tests rebind them in fixtures to inject
fakes.

Before :func:`astro_brain.app.build_app` has run, every provider raises
:class:`RuntimeError`. That forces us to fail fast if wiring is missing.
"""

from __future__ import annotations

from collections.abc import Callable

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import (
    GpsService,
    MountService,
    NetworkService,
    SystemInfoService,
    TrackingService,
)


def _not_wired() -> object:
    raise RuntimeError(
        "Service dependency not wired. Ensure build_app() was called."
    )


get_bus: Callable[[], StateBus] = _not_wired  # type: ignore[assignment]
get_mount: Callable[[], MountService] = _not_wired  # type: ignore[assignment]
get_tracking: Callable[[], TrackingService] = _not_wired  # type: ignore[assignment]
get_gps: Callable[[], GpsService] = _not_wired  # type: ignore[assignment]
get_network: Callable[[], NetworkService] = _not_wired  # type: ignore[assignment]
get_system_info: Callable[[], SystemInfoService] = _not_wired  # type: ignore[assignment]
