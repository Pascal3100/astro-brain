"""Application factory — wires services, deps, routes, and the orchestrator.

:func:`build_app` returns a fresh :class:`FastAPI` instance with:

* a dedicated :class:`~astro_brain.bus.StateBus`;
* services (fakes by default, real hardware adapters when
  ``use_hardware=True`` / ``ASTRO_BRAIN_HARDWARE=1``);
* every service installed on ``app.state`` so route-level ``Depends``
  resolvers in :mod:`astro_brain.deps` can reach them;
* a lifespan that starts each service, launches the orchestrator as a
  background task, and tears everything down on shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import FastAPI

from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.repository.state_db import db_path as _default_db_path
from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.calibration import router as calibration_router
from astro_brain.routes.commands import router as commands_router
from astro_brain.routes.events import router as events_router
from astro_brain.routes.state import router as state_router
from astro_brain.services.calibration import CalibrationServiceImpl
from astro_brain.services.fakes import (
    FakeGps,
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
    make_fake_calibration_adapters,
)


def _select_services(bus: StateBus, *, use_hardware: bool) -> dict[str, Any]:
    """Return the five services plus I2C adapters, either fakes or real hardware."""
    if use_hardware:
        from astro_brain.adapters.adxl345_adapter import (
            ADXL345_MOUNT_ADDR,
            ADXL345_TUBE_ADDR,
            Adxl345Adapter,
        )
        from astro_brain.adapters.gpsd_adapter import GpsdAdapter
        from astro_brain.adapters.lis3mdl_adapter import Lis3mdlAdapter
        from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = MountIndiAdapter(bus)
        # The mount adapter also implements ``set_tracking`` — re-use it
        # as the tracking service so ``/tracking`` drives real hardware.
        return {
            "mount": mount,
            "gps": GpsdAdapter(bus),
            "network": NetworkInfoAdapter(bus),
            "system": SystemInfoAdapter(bus),
            "tracking": mount,
            "adxl_mount": Adxl345Adapter(addr=ADXL345_MOUNT_ADDR),
            "adxl_tube": Adxl345Adapter(addr=ADXL345_TUBE_ADDR),
            "lis3mdl": Lis3mdlAdapter(),
        }
    fake_adxl_mount, fake_adxl_tube, fake_lis3mdl = make_fake_calibration_adapters()
    return {
        "mount": FakeMount(bus),
        "gps": FakeGps(bus),
        "network": FakeNetwork(bus),
        "system": FakeSystemInfo(bus),
        "tracking": FakeTracking(bus),
        "adxl_mount": fake_adxl_mount,
        "adxl_tube": fake_adxl_tube,
        "lis3mdl": fake_lis3mdl,
    }


def build_app(
    use_hardware: bool | None = None,
    *,
    db_path_override: str | Path | None = None,
) -> FastAPI:
    """Instantiate the FastAPI app with all services and background tasks wired.

    Parameters
    ----------
    use_hardware:
        When ``True`` the real hardware adapters are wired; ``False`` keeps
        the fakes. ``None`` falls back to the ``ASTRO_BRAIN_HARDWARE`` env var.
    db_path_override:
        Optional override for the on-disk state DB path. Tests typically pass
        ``":memory:"`` to get a fresh ephemeral database for the duration of
        the lifespan. ``None`` uses the production path from
        :func:`astro_brain.repository.state_db.db_path`.
    """
    if use_hardware is None:
        use_hardware = os.environ.get("ASTRO_BRAIN_HARDWARE", "0") == "1"

    bus = StateBus()
    services = _select_services(bus, use_hardware=use_hardware)
    orchestrator = Orchestrator(bus=bus, mount=services["mount"])

    background_tasks: list[asyncio.Task[Any]] = []

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        target = (
            db_path_override
            if db_path_override is not None
            else _default_db_path()
        )
        db_conn = await aiosqlite.connect(target)
        await run_migrations(db_conn)
        _app.state.db = db_conn

        calibration_service = CalibrationServiceImpl(
            db=db_conn,
            adxl_mount=services["adxl_mount"],
            adxl_tube=services["adxl_tube"],
            lis3mdl=services["lis3mdl"],
        )
        _app.state.calibration_service = calibration_service

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
            await db_conn.close()

    app = FastAPI(title="Astro-Brain", version="0.1.0", lifespan=lifespan)
    app.state.bus = bus
    app.state.mount = services["mount"]
    app.state.tracking = services["tracking"]
    app.state.gps = services["gps"]
    app.state.network = services["network"]
    app.state.system_info = services["system"]
    app.include_router(commands_router)
    app.include_router(state_router)
    app.include_router(events_router)
    app.include_router(calibration_router)
    return app


app = build_app()
