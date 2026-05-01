"""PyIndi.BaseClient subclass — bridges INDI callbacks to the StateBus.

This module imports ``PyIndi`` at the top level and is therefore only
loadable on the Pi (where ``python3-indi-client`` is installed via apt).
Workstation tests must NOT import it; they instantiate
``MountIndiAdapter(bus, client=FakeIndiClient(...))`` directly.

Responsibilities:

* Forward ``serverConnected`` / ``serverDisconnected`` to the bus
  (mount = ``error`` on disconnect — matches v0.1 watchdog semantics).
* No-op for ``newDevice`` / ``updateProperty`` for now; subsystems read
  property values on demand. Future enhancement (post-v0.2): forward
  ``EQUATORIAL_EOD_COORD`` updates so the bus exposes live coords.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import PyIndi  # type: ignore[import-not-found]

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class AstroBrainIndiClient(PyIndi.BaseClient):
    """Production INDI client. Pushes connection lifecycle to the bus."""

    def __init__(self, *, bus: StateBus) -> None:
        super().__init__()
        self._bus = bus

    # --- callbacks --------------------------------------------------------

    def serverConnected(self) -> None:  # noqa: N802 (PyIndi API name)
        logger.info("indi: server connected")

    def serverDisconnected(self, code: int) -> None:  # noqa: N802
        logger.warning("indi: server disconnected (code=%s)", code)
        self._bus.publish(
            "mount",
            SubsystemState(
                state="error",
                message=(
                    f"indiserver disconnected (code={code}). "
                    "Restart astro-brain.service to reconnect."
                ),
                since=_now(),
            ),
        )

    def newDevice(self, dev: PyIndi.BaseDevice) -> None:  # noqa: N802
        logger.info("indi: device available: %s", dev.getDeviceName())

    def newProperty(self, prop: PyIndi.Property) -> None:  # noqa: N802
        # Some PyIndi releases call newProperty for the first define;
        # later ones use updateProperty. Both safely no-op here.
        pass

    def updateProperty(self, prop: PyIndi.Property) -> None:  # noqa: N802
        # Property updates are pulled on-demand by MountIndiAdapter for now.
        pass

    def newMessage(self, dev: PyIndi.BaseDevice, msg_id: int) -> None:  # noqa: N802
        pass
