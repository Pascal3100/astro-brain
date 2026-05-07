"""About REST route — exposes backend version, network info, and uptime.

Mounted at ``GET /about``. No authentication required.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from astro_brain import __version__, deps
from astro_brain.services.interfaces import NetworkService, SystemInfoService

router = APIRouter(tags=["about"])


class AboutResponse(BaseModel):
    """Snapshot of backend metadata, network state, and system uptime."""

    backend_version: str
    app_version_seen: str | None = None
    mount_firmware: str | None = None
    ip: str | None
    ssid: str | None
    uptime_s: int | None
    started_at: str


@router.get("/about")
async def get_about(
    request: Request,
    network: NetworkService = Depends(deps.get_network),
    system_info: SystemInfoService = Depends(deps.get_system_info),
) -> AboutResponse:
    """Return a one-shot snapshot of backend identity and host state.

    Fields
    ------
    backend_version
        Package version from ``astro_brain.__version__``.
    app_version_seen
        Last ``X-App-Version`` header value sent by the Flutter client.
        Always ``null`` in v0.2 (header not yet consumed server-side).
    mount_firmware
        INDI ``DRIVER_INFO`` firmware string.
        TODO: extract from MountIndiAdapter when INDI is stable (post-Macro 1).
    ip, ssid
        Latest cached values from the network info adapter (no I/O).
    uptime_s
        Seconds since Pi boot, latest cached value.
    started_at
        ISO 8601 UTC timestamp of the backend process startup.
    """
    net = network.current_snapshot()
    sys = system_info.current_snapshot()
    started_at = request.app.state.started_at
    return AboutResponse(
        backend_version=__version__,
        app_version_seen=None,
        mount_firmware=None,
        ip=net.get("ip"),
        ssid=net.get("ssid"),
        uptime_s=sys.get("uptime_s"),
        started_at=started_at.isoformat(),
    )
