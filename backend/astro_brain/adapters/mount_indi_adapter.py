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
import logging
import os
from datetime import UTC, datetime
from typing import Any

from astro_brain.adapters._indi_property_helpers import set_switch_one_of_many
from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)

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
        self._goto_in_progress: bool = False
        self._goto_target: dict[str, Any] | None = None

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
            logger.exception("indi: start failed")
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
            logger.warning("indi: disconnect on stop raised", exc_info=True)
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

    # --- joystick / slew --------------------------------------------------

    _AXIS_TO_MOTION_VECTOR: dict[str, str] = {
        "alt": "TELESCOPE_MOTION_NS",
        "az": "TELESCOPE_MOTION_WE",
    }
    _AXIS_DIR_TO_ELEMENT: dict[tuple[str, str], tuple[str, str]] = {
        ("alt", "+"): ("MOTION_NORTH", "MOTION_SOUTH"),
        ("alt", "-"): ("MOTION_SOUTH", "MOTION_NORTH"),
        ("az", "+"): ("MOTION_WEST", "MOTION_EAST"),
        ("az", "-"): ("MOTION_EAST", "MOTION_WEST"),
    }

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        """Start a slew on ``axis`` in ``direction`` at ``rate`` (1–8).

        Pushes ``TELESCOPE_SLEW_RATE`` (1-of-many) then the appropriate
        ``TELESCOPE_MOTION_NS`` or ``TELESCOPE_MOTION_WE`` switch.
        Replaces any prior slew on the same axis (joystick semantics).
        """
        # TODO v0.3: read alt limits from app.state.db, clamp slew("alt", "+") near max_deg
        if self._device is None:
            return
        # Replace any existing slew on the same axis.
        self._active_slews = [s for s in self._active_slews if s["axis"] != axis]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )

        try:
            # 1. Push the slew rate (1-of-many switch).
            rate_vec = self._device.getSwitch("TELESCOPE_SLEW_RATE")
            if rate_vec is None:
                raise RuntimeError("TELESCOPE_SLEW_RATE property not found")
            set_switch_one_of_many(rate_vec, f"SLEW_RATE_{rate}")
            await asyncio.to_thread(self._client.sendNewProperty, rate_vec)

            # 2. Start motion on the correct axis.
            motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
            on_elem, off_elem = self._AXIS_DIR_TO_ELEMENT[(axis, direction)]
            motion_vec = self._device.getSwitch(motion_name)
            if motion_vec is None:
                raise RuntimeError(f"{motion_name} property not found")
            motion_vec[on_elem].setState("ON")
            motion_vec[off_elem].setState("OFF")
            await asyncio.to_thread(self._client.sendNewProperty, motion_vec)
        except Exception as exc:
            logger.exception("indi: slew failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return

        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "device": self._device_name,
                    "active_slews": [dict(s) for s in self._active_slews],
                },
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        """Stop slew on a single ``axis``, or abort all motion when ``None``.

        When ``axis`` is ``None`` uses ``TELESCOPE_ABORT_MOTION`` as a
        belt-and-braces stop covering anything still moving.
        """
        if self._device is None:
            return
        try:
            if axis is None:
                abort_vec = self._device.getSwitch("TELESCOPE_ABORT_MOTION")
                if abort_vec is None:
                    raise RuntimeError(
                        "TELESCOPE_ABORT_MOTION property not found"
                    )
                abort_vec["ABORT_MOTION"].setState("ON")
                await asyncio.to_thread(self._client.sendNewProperty, abort_vec)
                self._active_slews = []
            else:
                motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
                motion_vec = self._device.getSwitch(motion_name)
                if motion_vec is None:
                    raise RuntimeError(f"{motion_name} property not found")
                for elem in motion_vec:
                    elem.setState("OFF")
                await asyncio.to_thread(self._client.sendNewProperty, motion_vec)
                self._active_slews = [
                    s for s in self._active_slews if s["axis"] != axis
                ]
        except Exception as exc:
            logger.exception("indi: stop_slew failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return

        if self._active_slews:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="moving",
                    details={
                        "device": self._device_name,
                        "active_slews": [dict(s) for s in self._active_slews],
                    },
                    since=_now(),
                ),
            )
        else:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"device": self._device_name},
                    since=_now(),
                ),
            )

    # --- time / location --------------------------------------------------

    async def set_time(self, utc_iso: str) -> None:
        if self._device is None:
            return
        try:
            dt = datetime.fromisoformat(utc_iso)
            # INDI TIME_UTC.UTC expects ISO without tzinfo (UTC implicit).
            utc_naive = dt.astimezone(UTC).replace(tzinfo=None)
            time_vec = self._device.getText("TIME_UTC")
            if time_vec is None:
                raise RuntimeError("TIME_UTC property not found")
            time_vec["UTC"].setText(utc_naive.isoformat())
            time_vec["OFFSET"].setText("0")
            await asyncio.to_thread(self._client.sendNewProperty, time_vec)
        except Exception as exc:
            logger.exception("indi: set_time failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def set_location(self, lat: float, lon: float) -> None:
        if self._device is None:
            return
        try:
            geo = self._device.getNumber("GEOGRAPHIC_COORD")
            if geo is None:
                raise RuntimeError("GEOGRAPHIC_COORD property not found")
            geo["LAT"].setValue(float(lat))
            geo["LONG"].setValue(float(lon))
            # ELEV left at its current value (set by user/setup later).
            await asyncio.to_thread(self._client.sendNewProperty, geo)
        except Exception as exc:
            logger.exception("indi: set_location failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    # --- alignment sync (native Celestron model via INDI) ----------------

    async def sync_radec(self, ra_deg: float, dec_deg: float) -> None:
        """Push a sync point so the AUX driver builds its native model.

        Pattern: arm ``ON_COORD_SET=SYNC`` (1-of-many switch) then write
        ``EQUATORIAL_EOD_COORD`` (RA in hours, DEC in degrees, JNow). The
        driver consumes the sync and updates its internal alignment table.
        """
        if self._device is None:
            return
        try:
            mode = self._device.getSwitch("ON_COORD_SET")
            if mode is None:
                raise RuntimeError("ON_COORD_SET property not found")
            set_switch_one_of_many(mode, "SYNC")
            await asyncio.to_thread(self._client.sendNewProperty, mode)

            coord = self._device.getNumber("EQUATORIAL_EOD_COORD")
            if coord is None:
                raise RuntimeError("EQUATORIAL_EOD_COORD property not found")
            coord["RA"].setValue(float(ra_deg) / 15.0)
            coord["DEC"].setValue(float(dec_deg))
            await asyncio.to_thread(self._client.sendNewProperty, coord)
        except Exception as exc:
            logger.exception("indi: sync_radec failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    # --- goto (slew vers coordonnées + tracking sidéral natif) ------------

    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        if self._device is None:
            return
        try:
            mode = self._device.getSwitch("ON_COORD_SET")
            if mode is None:
                raise RuntimeError("ON_COORD_SET property not found")
            set_switch_one_of_many(mode, "TRACK")
            await asyncio.to_thread(self._client.sendNewProperty, mode)

            coord = self._device.getNumber("EQUATORIAL_EOD_COORD")
            if coord is None:
                raise RuntimeError("EQUATORIAL_EOD_COORD property not found")
            coord["RA"].setValue(float(ra_deg) / 15.0)
            coord["DEC"].setValue(float(dec_deg))
            await asyncio.to_thread(self._client.sendNewProperty, coord)
        except Exception as exc:
            logger.exception("indi: goto_radec failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return

        self._goto_in_progress = True
        self._goto_target = {
            "target_name": target_name,
            "ra_deg": float(ra_deg),
            "dec_deg": float(dec_deg),
        }
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "device": self._device_name,
                    "goto_in_progress": True,
                    "goto": dict(self._goto_target),
                },
                since=_now(),
            ),
        )

    # --- tracking (TrackingService surface) -------------------------------

    async def set_tracking(self, enabled: bool) -> None:
        if self._device is None:
            return
        try:
            track = self._device.getSwitch("TELESCOPE_TRACK_STATE")
            if track is None:
                raise RuntimeError("TELESCOPE_TRACK_STATE property not found")
            set_switch_one_of_many(
                track, "TRACK_ON" if enabled else "TRACK_OFF"
            )
            await asyncio.to_thread(self._client.sendNewProperty, track)
            self._bus.publish(
                "tracking",
                SubsystemState(
                    state="sidereal" if enabled else "off", since=_now()
                ),
            )
        except Exception as exc:
            logger.exception("indi: set_tracking failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    # --- cordwrap (AUX driver native) ------------------------------------

    _CORDWRAP_POS_ELEMENTS: dict[str, str] = {
        "N": "CORDWRAP_N",
        "E": "CORDWRAP_E",
        "S": "CORDWRAP_S",
        "W": "CORDWRAP_W",
    }

    async def cordwrap_get_enabled(self) -> bool:
        if self._device is None:
            return False
        cw = self._device.getSwitch("CORDWRAP")
        if cw is None:
            return False
        return cw["INDI_ENABLED"].getState() == "ON"

    async def cordwrap_set_enabled(self, enabled: bool) -> None:
        if self._device is None:
            return
        try:
            cw = self._device.getSwitch("CORDWRAP")
            if cw is None:
                raise RuntimeError("CORDWRAP property not found")
            set_switch_one_of_many(
                cw, "INDI_ENABLED" if enabled else "INDI_DISABLED"
            )
            await asyncio.to_thread(self._client.sendNewProperty, cw)
        except Exception as exc:
            logger.exception("indi: cordwrap_set_enabled failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def cordwrap_get_position(self) -> str:
        if self._device is None:
            return "N"
        cw_pos = self._device.getSwitch("CORDWRAP_POS")
        if cw_pos is None:
            return "N"
        for cardinal, elem_name in self._CORDWRAP_POS_ELEMENTS.items():
            if cw_pos[elem_name].getState() == "ON":
                return cardinal
        return "N"

    async def cordwrap_set_position(self, position: str) -> None:
        if position not in self._CORDWRAP_POS_ELEMENTS:
            raise ValueError(f"invalid cordwrap position: {position!r}")
        if self._device is None:
            return
        try:
            cw_pos = self._device.getSwitch("CORDWRAP_POS")
            if cw_pos is None:
                raise RuntimeError("CORDWRAP_POS property not found")
            set_switch_one_of_many(
                cw_pos, self._CORDWRAP_POS_ELEMENTS[position]
            )
            await asyncio.to_thread(self._client.sendNewProperty, cw_pos)
        except Exception as exc:
            logger.exception("indi: cordwrap_set_position failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    # --- backlash (driver patch required upstream) ----------------------

    _BACKLASH_ELEMENT: dict[tuple[str, str], str] = {
        ("az", "+"): "AZ_POS",
        ("az", "-"): "AZ_NEG",
        ("alt", "+"): "ALT_POS",
        ("alt", "-"): "ALT_NEG",
    }

    async def get_backlash(self, axis: Axis, direction: Direction) -> int:
        if self._device is None:
            return 0
        bl = self._device.getNumber("MOUNT_AXIS_BACKLASH")
        if bl is None:
            # Property missing -> driver not patched yet. Return 0 silently
            # so UI sliders still render; writes will surface the error.
            return 0
        elem_name = self._BACKLASH_ELEMENT[(axis, direction)]
        return int(bl[elem_name].getValue())

    async def set_backlash(
        self, axis: Axis, direction: Direction, value: int
    ) -> None:
        if not 0 <= int(value) <= 99:
            raise ValueError(f"backlash value out of range: {value}")
        if self._device is None:
            return
        try:
            bl = self._device.getNumber("MOUNT_AXIS_BACKLASH")
            if bl is None:
                raise RuntimeError(
                    "MOUNT_AXIS_BACKLASH not advertised by driver — "
                    "patch required (see plan Task 12)"
                )
            elem_name = self._BACKLASH_ELEMENT[(axis, direction)]
            bl[elem_name].setValue(float(int(value)))
            await asyncio.to_thread(self._client.sendNewProperty, bl)
        except Exception as exc:
            logger.exception("indi: set_backlash failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
