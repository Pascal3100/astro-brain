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
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import FastAPI

from astro_brain.alignment_invalidator import AlignmentInvalidator
from astro_brain.bus import StateBus
from astro_brain.mount_connection_supervisor import MountConnectionSupervisor
from astro_brain.orchestrator import Orchestrator
from astro_brain.repository import alignment_repo, site_repo
from astro_brain.repository.reference_db import (
    ReferenceDb,
    manifest_url,
    reference_path,
)
from astro_brain.repository.state_db import db_path as _default_db_path
from astro_brain.repository.state_db import run_migrations
from astro_brain.routes.about import router as about_router
from astro_brain.routes.alignment import router as alignment_router
from astro_brain.routes.commands import router as commands_router
from astro_brain.routes.events import router as events_router
from astro_brain.routes.goto import router as goto_router
from astro_brain.routes.reference import router as reference_router
from astro_brain.routes.site import router as site_router
from astro_brain.routes.state import router as state_router
from astro_brain.services._alignment_catalog import (
    MountLimits,
    Observer,
    select_candidates,
    sky_az_alt_from_ra_dec,
)
from astro_brain.services.alignment import AlignmentServiceImpl
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)
from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
from astro_brain.services.catalog.resolver import TargetResolver
from astro_brain.services.fakes import (
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
)
from astro_brain.services.reference.sync import ReferenceSync
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)


async def _boot_reference_sync(reference_sync: ReferenceSync) -> None:
    """Run the boot `reference.sqlite` sync, surfacing unexpected failures.

    :meth:`ReferenceSync.sync` already handles and logs its expected
    outcomes. This wrapper exists so anything it does *not* expect (full
    disk, unreadable cache) reaches journald instead of dying silently as a
    never-retrieved task exception.
    """
    try:
        await reference_sync.sync()
    except Exception:
        logger.exception("reference: sync au boot échouée")


class _AlignmentSensorsBridge:
    """Expose la position d'observation sous l'interface duck-typée
    (`position`, `sky_az_alt_for`) qu'attend AlignmentServiceImpl.

    Chaîne de position : site d'observation persisté → None. Le site est semé
    au boot depuis ``observing_site`` et réécrit à chaud par ``PUT /site``.
    Plus de fix GPS local, plus de fallback codé en dur.
    """

    def __init__(self) -> None:
        self._site: tuple[float, float] | None = None

    def set_site(self, lat: float, lon: float) -> None:
        """Set the persisted observing site position (in-memory copy)."""
        self._site = (lat, lon)

    def clear_site(self) -> None:
        """Clear the in-memory observing site position."""
        self._site = None

    def site(self) -> tuple[float, float] | None:
        """Return the in-memory copy of the persisted observing site."""
        return self._site

    def position(self) -> tuple[float, float] | None:
        """Return the observing site position, or ``None`` if never set."""
        return self._site

    def observer(self) -> Observer | None:
        pos = self.position()
        if pos is None:
            return None
        return Observer(lat_deg=pos[0], lon_deg=pos[1])

    def sky_az_alt_for(self, star: Any) -> tuple[float, float] | None:
        obs = self.observer()
        if obs is None:
            return None
        return sky_az_alt_from_ra_dec(
            star.ra_deg, star.dec_deg, obs, datetime.now(UTC)
        )


def _select_services(bus: StateBus, *, use_hardware: bool) -> dict[str, Any]:
    """Return the four services, either fakes or real hardware adapters."""
    if use_hardware:
        from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = MountIndiAdapter(bus)
        # The mount adapter also implements ``set_tracking`` — re-use it
        # as the tracking service so ``/tracking`` drives real hardware.
        return {
            "mount": mount,
            "network": NetworkInfoAdapter(bus),
            "system": SystemInfoAdapter(bus),
            "tracking": mount,
        }
    return {
        "mount": FakeMount(bus),
        "network": FakeNetwork(bus),
        "system": FakeSystemInfo(bus),
        "tracking": FakeTracking(bus),
    }


def build_app(
    use_hardware: bool | None = None,
    *,
    db_path_override: str | Path | None = None,
    sync_on_boot: bool | None = None,
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
    sync_on_boot:
        Whether to launch a background `reference.sqlite` sync at startup.
        ``None`` falls back to the ``ASTRO_BRAIN_REFERENCE_SYNC_ON_BOOT`` env
        var (default: sync).
    """
    if use_hardware is None:
        use_hardware = os.environ.get("ASTRO_BRAIN_HARDWARE", "0") == "1"

    bus = StateBus()
    services = _select_services(bus, use_hardware=use_hardware)
    reconnect_supervisor = MountConnectionSupervisor(
        bus=bus, mount=services["mount"]
    )

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

        # base référence (reference.sqlite) — fichier distinct, RO, jetable
        if db_path_override in (None, ":memory:") or str(target) == ":memory:":
            ref_path = reference_path()
        else:
            ref_path = Path(target).parent / "reference.sqlite"
        reference_db = ReferenceDb(ref_path)
        await reference_db.open()
        _app.state.reference_db = reference_db

        fixed = FixedObjectProvider(reference_db)
        ephemeris = EphemerisProvider(reference_db, now_utc=lambda: datetime.now(UTC))
        catalog = ReferenceCatalog(fixed=fixed, ephemeris=ephemeris,
                                    reference=reference_db)
        _app.state.resolver = TargetResolver(catalog)

        reference_sync = ReferenceSync(reference=reference_db,
                                        manifest_url=manifest_url())
        _app.state.reference_sync = reference_sync

        do_sync = (sync_on_boot if sync_on_boot is not None
                   else os.environ.get("ASTRO_BRAIN_REFERENCE_SYNC_ON_BOOT", "1") != "0")
        if do_sync:
            background_tasks.append(
                asyncio.create_task(
                    _boot_reference_sync(reference_sync),
                    name="reference-boot-sync",
                )
            )

        _app.state.started_at = datetime.now(UTC)

        sensors_bridge = _AlignmentSensorsBridge()
        stored_site = await site_repo.get_site(db_conn)
        if stored_site is not None:
            sensors_bridge.set_site(stored_site.lat, stored_site.lon)
        _app.state.position_provider = sensors_bridge

        def _candidates_provider() -> list[Any]:
            obs = sensors_bridge.observer()
            if obs is None:
                return []
            limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
            return select_candidates(obs, datetime.now(UTC), limits, exclude_ids=set())

        _app.state.alignment = AlignmentServiceImpl(
            select_candidates=_candidates_provider,
            mount=services["mount"],
            tracking=services["tracking"],
            sensors=sensors_bridge,
            repo_save=alignment_repo.save,
            repo_load=alignment_repo.load,
            repo_clear=alignment_repo.clear,
            db=db_conn,
            now_utc=lambda: datetime.now(UTC),
        )
        bus.publish(
            "alignment",
            SubsystemState(state="idle", details={"is_aligned": False}, since=datetime.now(UTC)),
        )

        invalidator = AlignmentInvalidator(
            alignment=_app.state.alignment, bus=bus
        )
        background_tasks.append(
            asyncio.create_task(invalidator.run(), name="alignment-invalidator")
        )
        # Le site étant déjà semé depuis SQLite, la garde ΔGPS de
        # ``alignment_repo.load`` est évaluable dès le boot : plus besoin
        # d'attendre un fix, on réhydrate directement.
        if await _app.state.alignment.rehydrate():
            bus.publish(
                "alignment",
                SubsystemState(
                    state="idle",
                    details={"is_aligned": True},
                    since=datetime.now(UTC),
                ),
            )

        await services["mount"].start()
        await services["network"].start()
        await services["system"].start()

        # Construit ici et non dans `build_app` : l'orchestrateur consomme le
        # provider de position, lui-même bâti dans ce lifespan.
        orchestrator = Orchestrator(
            bus=bus, mount=services["mount"], position=sensors_bridge
        )
        orch_task = asyncio.create_task(orchestrator.run(), name="orchestrator")
        background_tasks.append(orch_task)
        background_tasks.append(
            asyncio.create_task(
                reconnect_supervisor.run(), name="mount-reconnect-supervisor"
            )
        )
        try:
            yield
        finally:
            for task in background_tasks:
                task.cancel()
            for task in background_tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await services["mount"].stop()
            await services["network"].stop()
            await services["system"].stop()
            await reference_db.close()
            await db_conn.close()

    app = FastAPI(title="Astro-Brain", version="0.1.0", lifespan=lifespan)
    app.state.bus = bus
    app.state.mount = services["mount"]
    app.state.tracking = services["tracking"]
    app.state.network = services["network"]
    app.state.system_info = services["system"]
    app.include_router(about_router)
    app.include_router(commands_router)
    app.include_router(state_router)
    app.include_router(events_router)
    app.include_router(site_router)
    app.include_router(alignment_router)
    app.include_router(goto_router)
    app.include_router(reference_router)
    return app


app = build_app()
