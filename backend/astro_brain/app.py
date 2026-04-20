"""Application factory — wires services, deps, routes, and the orchestrator.

:func:`build_app` returns a fresh :class:`FastAPI` instance with:

* a dedicated :class:`~astro_brain.bus.StateBus`;
* services (fakes by default, real hardware adapters when
  ``use_hardware=True`` / ``ASTRO_BRAIN_HARDWARE=1``);
* the ``deps`` module rebound so routes resolve the current instances;
* a lifespan that starts each service, launches the orchestrator as a
  background task, and tears everything down on shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.routes.commands import router as commands_router
from astro_brain.routes.events import router as events_router
from astro_brain.routes.state import router as state_router
from astro_brain.services.fakes import (
    FakeGps,
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
)


def _select_services(bus: StateBus, *, use_hardware: bool) -> dict[str, Any]:
    """Return the five services, either fakes or real hardware adapters."""
    if use_hardware:
        from astro_brain.adapters.gpsd_adapter import GpsdAdapter
        from astro_brain.adapters.nexstar_adapter import NexStarMountAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = NexStarMountAdapter(bus)
        # The mount adapter also implements ``set_tracking`` — re-use it
        # as the tracking service so ``/tracking`` drives real hardware.
        return {
            "mount": mount,
            "gps": GpsdAdapter(bus),
            "network": NetworkInfoAdapter(bus),
            "system": SystemInfoAdapter(bus),
            "tracking": mount,
        }
    return {
        "mount": FakeMount(bus),
        "gps": FakeGps(bus),
        "network": FakeNetwork(bus),
        "system": FakeSystemInfo(bus),
        "tracking": FakeTracking(bus),
    }


def build_app(use_hardware: bool | None = None) -> FastAPI:
    """Instantiate the FastAPI app with all services and background tasks wired."""
    if use_hardware is None:
        use_hardware = os.environ.get("ASTRO_BRAIN_HARDWARE", "0") == "1"

    bus = StateBus()
    services = _select_services(bus, use_hardware=use_hardware)
    orchestrator = Orchestrator(bus=bus, mount=services["mount"])

    deps.get_bus = lambda: bus
    deps.get_mount = lambda: services["mount"]
    deps.get_tracking = lambda: services["tracking"]
    deps.get_gps = lambda: services["gps"]
    deps.get_network = lambda: services["network"]
    deps.get_system_info = lambda: services["system"]

    background_tasks: list[asyncio.Task[Any]] = []

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await services["mount"].start()
        await services["gps"].start()
        await services["network"].start()
        await services["system"].start()

        orch_task = asyncio.create_task(orchestrator.run(), name="orchestrator")
        background_tasks.append(orch_task)
        try:
            yield
        finally:
            for task in background_tasks:
                task.cancel()
            for task in background_tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await services["mount"].stop()
            await services["gps"].stop()
            await services["network"].stop()
            await services["system"].stop()

    app = FastAPI(title="Astro-Brain", version="0.1.0", lifespan=lifespan)
    app.include_router(commands_router)
    app.include_router(state_router)
    app.include_router(events_router)
    return app


app = build_app()
