"""Dependency resolvers for FastAPI routes.

Services live on ``app.state`` — populated by :func:`astro_brain.app.build_app`
(or by a test fixture). Each resolver below is a ``Depends``-compatible
callable that reads its target off the request's app instance. Routes
should declare their collaborators via ``Depends(deps.get_<name>)``.

The legacy pattern (module-level rebinding, e.g. ``deps.get_bus = lambda: ...``)
has been removed: it forced every app instance in the process to share
state, which broke when two apps co-existed (real + test). Tests now
build their own ``FastAPI`` instance and set ``app.state.*`` directly.
"""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import Request

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import (
    CalibrationService,
    GpsService,
    MountService,
    NetworkService,
    SystemInfoService,
    TrackingService,
)


def get_bus(request: Request) -> StateBus:
    return request.app.state.bus


def get_mount(request: Request) -> MountService:
    return request.app.state.mount


def get_tracking(request: Request) -> TrackingService:
    return request.app.state.tracking


def get_gps(request: Request) -> GpsService:
    return request.app.state.gps


def get_network(request: Request) -> NetworkService:
    return request.app.state.network


def get_system_info(request: Request) -> SystemInfoService:
    return request.app.state.system_info


def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


def get_calibration_service(request: Request) -> CalibrationService:
    return request.app.state.calibration_service


def get_adxl_mount(request: Request) -> Any:
    return request.app.state.adxl_mount


def get_adxl_tube(request: Request) -> Any:
    return request.app.state.adxl_tube


def get_lis3mdl(request: Request) -> Any:
    return request.app.state.lis3mdl


def get_lazy_adxl_mount(request: Request) -> Any:
    return request.app.state.lazy_adxl_mount


def get_lazy_adxl_tube(request: Request) -> Any:
    return request.app.state.lazy_adxl_tube


def get_lazy_lis3mdl(request: Request) -> Any:
    return request.app.state.lazy_lis3mdl
