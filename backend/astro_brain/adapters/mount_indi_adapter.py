"""INDI-based mount adapter — replaces NexStarMountAdapter.

Implements the same ``MountService`` + ``TrackingService`` interface as
the previous nexstarpy-based adapter. Each high-level method translates
to a property push against ``indiserver`` via ``pyindi-client``.

The PyIndi client is **injected** at construction time, so tests pass a
``FakeIndiClient``. In production, ``app.py`` constructs the real
``MountIndiAdapter`` which builds an ``AstroBrainIndiClient`` (subclass
of ``PyIndi.BaseClient``) under the hood.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction  # noqa: F401
from astro_brain.subsystems import SubsystemState

INDI_HOST_ENV = "ASTRO_BRAIN_INDI_HOST"
INDI_HOST_DEFAULT = "127.0.0.1"
INDI_PORT_ENV = "ASTRO_BRAIN_INDI_PORT"
INDI_PORT_DEFAULT = 7624
INDI_DEVICE_NAME = "Celestron AUX"
SERIAL_DEVICE_ENV = "ASTRO_BRAIN_SERIAL_DEVICE"
SERIAL_DEVICE_DEFAULT = "/dev/ttyUSB0"
DEVICE_DISCOVERY_TIMEOUT_S = 5.0
DEVICE_DISCOVERY_POLL_S = 0.1


def _now() -> datetime:
    return datetime.now(UTC)


class MountIndiAdapter:
    """Drives the Celestron mount through indiserver + indi_celestron_aux."""

    def __init__(
        self,
        bus: StateBus,
        *,
        client: Any | None = None,
        host: str | None = None,
        port: int | None = None,
        device_name: str = INDI_DEVICE_NAME,
        serial_device: str | None = None,
    ) -> None:
        self._bus = bus
        self._client = client  # injected fake or built lazily in start()
        self._host = host or os.environ.get(INDI_HOST_ENV, INDI_HOST_DEFAULT)
        port_str = os.environ.get(INDI_PORT_ENV, str(INDI_PORT_DEFAULT))
        self._port = port if port is not None else int(port_str)
        self._device_name = device_name
        self._serial_device = serial_device or os.environ.get(
            SERIAL_DEVICE_ENV, SERIAL_DEVICE_DEFAULT
        )
        self._device: Any | None = None
        self._active_slews: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Connect to indiserver and discover the mount device.

        Publishes ``connecting`` then ``ready`` on success, or ``error``
        on any exception. Also initialises the ``tracking`` subsystem to
        ``off``.
        """
        self._bus.publish(
            "mount", SubsystemState(state="connecting", since=_now())
        )
        self._bus.publish(
            "tracking", SubsystemState(state="off", since=_now())
        )
        try:
            if self._client is None:
                # Production path: lazy import to keep the module
                # importable on a workstation without libindi.
                from astro_brain.adapters.indi_client import (  # type: ignore[import]
                    AstroBrainIndiClient,
                )

                self._client = AstroBrainIndiClient(bus=self._bus)
            self._client.setServer(self._host, self._port)
            ok = await asyncio.to_thread(self._client.connectServer)
            if not ok:
                raise RuntimeError(
                    f"connectServer returned False ({self._host}:{self._port})"
                )
            self._device = await self._await_device()
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"device": self._device_name},
                    since=_now(),
                ),
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def stop(self) -> None:
        """Disconnect from indiserver and publish ``disconnected``."""
        try:
            if self._client is not None:
                await asyncio.to_thread(self._client.disconnectServer)
        except Exception:
            pass
        self._device = None
        self._bus.publish(
            "mount", SubsystemState(state="disconnected", since=_now())
        )

    async def _await_device(self) -> Any:
        """Poll ``getDevice`` until the device shows up or we time out."""
        deadline = asyncio.get_running_loop().time() + DEVICE_DISCOVERY_TIMEOUT_S
        while asyncio.get_running_loop().time() < deadline:
            dev = self._client.getDevice(self._device_name)
            if dev is not None:
                return dev
            await asyncio.sleep(DEVICE_DISCOVERY_POLL_S)
        raise TimeoutError(
            f"INDI device {self._device_name!r} not advertised within "
            f"{DEVICE_DISCOVERY_TIMEOUT_S}s"
        )
