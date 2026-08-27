"""INDI-based mount adapter — replaces NexStarMountAdapter.

Implements the same ``MountService`` + ``TrackingService`` interface as
the previous nexstarpy-based adapter. Each high-level method translates
to a property push against ``indiserver`` via ``pyindi-client``.

The PyIndi client is **injected** at construction time, so tests pass a
``FakeIndiClient``. In production, ``app.py`` constructs the real
``MountIndiAdapter`` which builds an ``AstroBrainIndiClient`` (subclass
of ``PyIndi.BaseClient``) under the hood.

**Link layer — mode Serial on ``/dev/ttyAMA0``.** The ESP32 bridge sits on
the AUX bus and relays it to the Pi over three wires on UART0 (19200 8N2,
the rate ``indi_celestron_aux`` imposes: ``setDefaultBaudRate(B_19200)``).
:meth:`MountIndiAdapter._configure_serial_link` pushes ``CONNECTION_MODE``,
``DEVICE_PORT`` and ``PORT_TYPE`` from code before connecting, so the link
no longer depends on the unversioned ``~/.indi/Celestron AUX_config.xml``.

Why serial rather than the bridge's old WiFi/TCP mode: in Network mode the
driver's ``tcpReadResponse()`` returns ``true`` unconditionally as soon as
the socket is open — a mount that answers nothing looks like a success, a
false positive that cost half a session (journal S51). ``serialReadResponse()``
blocks with a timeout and returns ``false``, so a dead bus reads as a
failure. See ADR 2026-08-26.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from astro_brain.adapters._indi_property_helpers import (
    SWITCH_OFF,
    SWITCH_ON,
    as_switch_vector,
    find_widget,
    set_switch_one_of_many,
)
from astro_brain.bus import StateBus
from astro_brain.services.interfaces import (
    Axis,
    Direction,
    SensorUnavailableError,
)
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)

INDI_HOST_ENV = "ASTRO_BRAIN_INDI_HOST"
INDI_HOST_DEFAULT = "127.0.0.1"
INDI_PORT_ENV = "ASTRO_BRAIN_INDI_PORT"
INDI_PORT_DEFAULT = 7624
INDI_DEVICE_NAME = "Celestron AUX"
SERIAL_DEVICE_ENV = "ASTRO_BRAIN_SERIAL_DEVICE"
SERIAL_DEVICE_DEFAULT = "/dev/ttyAMA0"  # UART0 GPIO — pont ESP32 filaire
DEVICE_DISCOVERY_TIMEOUT_S = 5.0
DEVICE_DISCOVERY_POLL_S = 0.1
CONNECT_CONFIRM_TIMEOUT_S = 8.0
PROPERTY_READY_TIMEOUT_S = 5.0
ENCODER_ANGLES_PROPERTY = "TELESCOPE_ENCODER_ANGLES"


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
        self._connected: bool = False
        self._active_slews: list[dict[str, Any]] = []
        self._goto_in_progress: bool = False
        self._goto_target: dict[str, Any] | None = None
        #: Dernier état de suivi publié, pour ne pas rejouer les échos
        #: identiques du driver sur le bus (cf. _publish_track_state).
        self._last_track_state: str | None = None
        self._reconnect_lock = asyncio.Lock()
        self._pending_reconnects: set[asyncio.Task[None]] = set()

    def _publish_error(
        self, exc: Exception, *, context: str, state: str = "error"
    ) -> None:
        """Log ``exc`` and publish it as a ``mount`` state.

        Shared by every INDI call site that fails with an exception: logs
        with ``logger.exception`` (full traceback) using the exact message
        each site used before extraction (``"indi: {context} failed"``),
        then publishes ``state`` (``"error"`` for command failures,
        ``"disconnected"`` for :meth:`reconnect`, which must leave the
        supervisor free to keep retrying rather than surface an error).
        """
        logger.exception("indi: %s failed", context)
        self._bus.publish(
            "mount",
            SubsystemState(state=state, message=str(exc), since=_now()),
        )

    @property
    def _device(self) -> Any | None:
        """Live device handle — re-fetched on every access, never cached.

        A pyindi ``BaseDevice`` reference grabbed too early (before the
        driver has defined its properties) goes stale: it exposes empty
        property vectors (device name ``""``, nameless widgets). Fetching
        it fresh each time returns the populated device. See journal S37.
        """
        if not self._connected or self._client is None:
            return None
        return self._client.getDevice(self._device_name)

    async def start(self) -> None:
        """Connect to indiserver and discover the mount device.

        Publishes ``connecting`` then ``ready`` on success, or ``error``
        on any exception. Also initialises the ``tracking`` subsystem to
        ``off``. ``ready`` waits on :meth:`_await_mount_alive`: reaching
        ``CONNECT=On`` is not enough, the mount must have answered.
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

                self._client = AstroBrainIndiClient(
                    bus=self._bus,
                    on_update=self.handle_property_update,
                    on_disconnect=self.handle_server_disconnected,
                )
            self._client.setServer(self._host, self._port)
            ok = await asyncio.to_thread(self._client.connectServer)
            if not ok:
                raise RuntimeError(
                    f"connectServer returned False ({self._host}:{self._port})"
                )
            await self._await_device()
            await self._ensure_connected()
            await self._await_mount_alive()
            self._connected = True
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"device": self._device_name},
                    since=_now(),
                ),
            )
        except Exception as exc:
            self._publish_error(exc, context="start")

    async def stop(self) -> None:
        """Disconnect from indiserver and publish ``disconnected``."""
        try:
            if self._client is not None:
                await asyncio.to_thread(self._client.disconnectServer)
        except Exception:
            logger.warning("indi: disconnect on stop raised", exc_info=True)
        self._connected = False
        self._bus.publish(
            "mount", SubsystemState(state="disconnected", since=_now())
        )

    def handle_server_disconnected(self, code: int) -> None:
        """React to indiserver dropping (invoked on the asyncio loop).

        The PyIndi client forwards its ``serverDisconnected`` callback here.
        A dropped link is **not** a transient command error: we publish
        ``disconnected`` (which :class:`MountConnectionSupervisor` watches
        to trigger reconnection) and reserve ``error`` for recoverable
        command failures. Flipping ``_connected`` also stops :attr:`_device`
        from handing out a stale handle. See journal S38.
        """
        self._connected = False
        self._bus.publish(
            "mount",
            SubsystemState(
                state="disconnected",
                message=f"indiserver disconnected (code={code})",
                since=_now(),
            ),
        )

    async def reconnect(self) -> None:
        """Re-establish the mount link end-to-end (manual or supervisor).

        Serialised by a lock so a manual nudge and the background
        supervisor never race. Reuses the boot connect sequence: reconnect
        to indiserver if the socket dropped, rediscover the device, push
        ``CONNECTION.CONNECT=On`` via :meth:`_ensure_connected`, then wait
        for the mount to actually answer (:meth:`_await_mount_alive`). On
        failure it publishes ``disconnected`` (not ``error``) so the
        supervisor keeps retrying.
        """
        async with self._reconnect_lock:
            if self._client is None:
                await self.start()
                return
            self._bus.publish(
                "mount", SubsystemState(state="connecting", since=_now())
            )
            try:
                if not self._client.isServerConnected():
                    self._client.setServer(self._host, self._port)
                    ok = await asyncio.to_thread(self._client.connectServer)
                    if not ok:
                        raise RuntimeError(
                            f"connectServer returned False "
                            f"({self._host}:{self._port})"
                        )
                await self._await_device()
                await self._ensure_connected()
                await self._await_mount_alive()
                self._connected = True
                self._bus.publish(
                    "mount",
                    SubsystemState(
                        state="ready",
                        details={"device": self._device_name},
                        since=_now(),
                    ),
                )
            except Exception as exc:
                self._connected = False
                self._publish_error(
                    exc, context="reconnect", state="disconnected"
                )

    def request_reconnect(self) -> None:
        """Schedule a reconnect without blocking the caller.

        Used by ``POST /mount/reconnect``: the REST call returns
        immediately (the app has a short timeout) and connection progress
        flows back over SSE.
        """
        task = asyncio.create_task(self.reconnect())
        self._pending_reconnects.add(task)
        task.add_done_callback(self._pending_reconnects.discard)

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

    async def _await_connection_switch(self) -> Any | None:
        """Poll until the ``CONNECTION`` switch exposes its ``CONNECT`` widget.

        Right after :meth:`connectServer` the driver's property tree is still
        streaming in over the socket: ``getDevice`` can hand back a
        placeholder whose ``CONNECTION`` vector holds nameless widgets
        (same stale-handle family as journal S37/S38). Reading ``CONNECT``
        the instant the device appears raised ``KeyError: 'CONNECT'`` and
        failed ``start()`` on hardware. Poll (re-fetching the device each
        time, since the handle is never cached) until the named widget shows
        up. Returns ``None`` if the device genuinely never advertises a
        ``CONNECTION`` switch — only bare fakes, left as-is by the caller.
        """
        deadline = (
            asyncio.get_running_loop().time() + CONNECT_CONFIRM_TIMEOUT_S
        )
        saw_switch = False
        while asyncio.get_running_loop().time() < deadline:
            dev = self._client.getDevice(self._device_name)
            conn = dev.getSwitch("CONNECTION") if dev is not None else None
            if conn is not None:
                saw_switch = True
                if conn.findWidgetByName("CONNECT") is not None:
                    return conn
            elif not saw_switch:
                # Never advertised a CONNECTION switch: a bare fake, not the
                # real driver (which returns a placeholder within ~20 ms).
                return None
            await asyncio.sleep(DEVICE_DISCOVERY_POLL_S)
        return None

    async def _await_widgets(
        self,
        fetch: Callable[[Any], Any],
        *,
        widgets: tuple[str, ...],
        context: str,
    ) -> Any:
        """Poll until ``fetch`` yields a vector exposing every named widget.

        Generalises :meth:`_await_connection_switch` to any property. The
        driver's property tree streams in over the socket *after* the device
        is advertised, so a vector fetched the instant ``start()`` publishes
        ``ready`` can be a placeholder holding nameless widgets — reading one
        raises ``KeyError`` (journal S37/S38). The boot sync hit exactly that:
        ``GEOGRAPHIC_COORD`` was already fetchable while ``LAT`` was not, and
        the mount pill flipped to ``error`` with the cryptic message ``'LAT'``.

        ``fetch`` receives a freshly-fetched device handle (never a cached
        one) and returns the vector or ``None``.

        Raises:
            TimeoutError: if the widgets are still missing after
                :data:`PROPERTY_READY_TIMEOUT_S` — a genuinely absent
                property rather than a slow one.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + PROPERTY_READY_TIMEOUT_S
        while True:
            dev = self._client.getDevice(self._device_name)
            vector = fetch(dev) if dev is not None else None
            if vector is not None and all(
                vector.findWidgetByName(name) is not None for name in widgets
            ):
                return vector
            if loop.time() >= deadline:
                raise TimeoutError(
                    f"{context}: widgets {', '.join(widgets)} not defined "
                    f"within {PROPERTY_READY_TIMEOUT_S}s"
                )
            await asyncio.sleep(DEVICE_DISCOVERY_POLL_S)

    async def _configure_serial_link(self) -> None:
        """Pin the link layer to Serial on :attr:`_serial_device`.

        Pushed **before** ``CONNECTION.CONNECT`` — the driver reads the link
        settings when it opens the link, and refuses to change them while
        connected. Order matters: ``CONNECTION_MODE`` first, because
        ``indi_celestron_aux`` only (re)defines ``DEVICE_PORT`` once it is in
        Serial mode; then the port; then ``PORT_TYPE``, which tells the driver
        the far end is the raw **AUX bus** (the ESP32 bridge) and not a hand
        controller's USB pass-through.

        Doing this from code rather than from ``~/.indi/Celestron AUX_config.xml``
        keeps the link reproducible: the config file is unversioned, lives only
        on the Pi, and silently resurrects the old TCP settings on a fresh
        install.

        A driver that advertises no ``CONNECTION_MODE`` (never the real one;
        only bare fakes) is left with whatever it loaded from its own config.
        """
        mode = await self._await_optional_switch(
            "CONNECTION_MODE", widget="CONNECTION_SERIAL"
        )
        if mode is None:
            logger.warning(
                "indi: no CONNECTION_MODE property; leaving the driver's own "
                "link configuration untouched"
            )
            return
        set_switch_one_of_many(mode, "CONNECTION_SERIAL")
        await asyncio.to_thread(self._client.sendNewProperty, mode)
        logger.info("indi: CONNECTION_MODE=CONNECTION_SERIAL")

        # From here the driver is in Serial mode, so both vectors are due:
        # a miss is a real fault, and _await_widgets raises rather than
        # letting us connect on a stale port.
        port = await self._await_widgets(
            lambda dev: dev.getText("DEVICE_PORT"),
            widgets=("PORT",),
            context="DEVICE_PORT",
        )
        find_widget(port, "PORT").setText(self._serial_device)
        await asyncio.to_thread(self._client.sendNewProperty, port)
        logger.info("indi: DEVICE_PORT=%s", self._serial_device)

        port_type = await self._await_widgets(
            lambda dev: dev.getSwitch("PORT_TYPE"),
            widgets=("PORT_AUX_PC",),
            context="PORT_TYPE",
        )
        set_switch_one_of_many(port_type, "PORT_AUX_PC")
        await asyncio.to_thread(self._client.sendNewProperty, port_type)
        logger.info("indi: PORT_TYPE=PORT_AUX_PC")

    async def _await_optional_switch(
        self, name: str, *, widget: str
    ) -> Any | None:
        """Poll for a switch vector, returning ``None`` if never advertised.

        Same shape as :meth:`_await_connection_switch`, for a property whose
        absence is tolerable: a device that has not advertised ``name`` on the
        very first look is a bare fake, since the real driver defines all of
        its ``initProperties`` vectors in the same burst as ``CONNECTION``
        (already awaited by the caller). Once seen, we still wait for the
        named widget — the vector can land as a nameless placeholder.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + PROPERTY_READY_TIMEOUT_S
        seen = False
        while loop.time() < deadline:
            dev = self._client.getDevice(self._device_name)
            vector = dev.getSwitch(name) if dev is not None else None
            if vector is not None:
                seen = True
                if vector.findWidgetByName(widget) is not None:
                    return vector
            elif not seen:
                return None
            await asyncio.sleep(DEVICE_DISCOVERY_POLL_S)
        logger.warning("indi: %s.%s never became readable", name, widget)
        return None

    async def _ensure_connected(self) -> None:
        """Push ``CONNECTION.CONNECT=On`` and wait for the driver to confirm.

        indiserver *advertises* the device (so :meth:`_await_device`
        succeeds) even while the ``indi_celestron_aux`` driver is
        disconnected from the mount. In that state the driver has not
        defined any mount property (``TELESCOPE_SLEW_RATE``, motion
        switches, …), so every command silently no-ops — which is exactly
        why the app's manual mode moved nothing until the connection was
        toggled by hand (journal S38). Connecting here makes the mount
        usable straight after :meth:`start` without manual intervention.

        A driver that exposes no ``CONNECTION`` property (never the real
        one; only bare fakes) is left as-is. On a driver that *is* about to
        connect, :meth:`_configure_serial_link` runs first: the link settings
        only take effect if they are pushed before ``CONNECT``.
        """
        conn = await self._await_connection_switch()
        if conn is None:
            logger.warning("indi: no CONNECTION property; skipping connect")
            return
        if find_widget(conn, "CONNECT").getState() == SWITCH_ON:
            return  # already connected
        await self._configure_serial_link()
        set_switch_one_of_many(conn, "CONNECT")
        await asyncio.to_thread(self._client.sendNewProperty, conn)

        # Wait for CONNECT to read back On (driver confirmed the link).
        deadline = asyncio.get_running_loop().time() + CONNECT_CONFIRM_TIMEOUT_S
        while asyncio.get_running_loop().time() < deadline:
            fresh = self._client.getDevice(self._device_name).getSwitch(
                "CONNECTION"
            )
            if fresh is not None and (
                find_widget(fresh, "CONNECT").getState() == SWITCH_ON
            ):
                return
            await asyncio.sleep(DEVICE_DISCOVERY_POLL_S)
        raise TimeoutError(
            f"mount did not confirm CONNECTION within "
            f"{CONNECT_CONFIRM_TIMEOUT_S}s"
        )

    #: Property ``indi_celestron_aux`` only defines once ALT and AZM have
    #: replied -- and the very one the joystick needs.
    ALIVE_PROPERTY = "TELESCOPE_SLEW_RATE"
    #: One of its widgets, named only once the property tree has streamed in.
    ALIVE_WIDGET = "1x"

    async def _await_mount_alive(self) -> None:
        """Wait for a property that only a mount that answered can produce.

        ``CONNECTION.CONNECT`` reading ``On`` is **not** proof of a working
        link: the driver leaves the switch on after a failed open, so
        :meth:`_ensure_connected` short-circuits on ``already connected`` and
        we published ``ready`` over a mount that had answered nothing --
        ten green seconds on a powered-off mount before the boot sync timed
        out and flipped the pill to ``error`` (journal S57). That is the same
        family of false positive as ``tcpReadResponse()`` returning ``true``
        on a bare open socket, which the move to Serial set out to kill; a
        switch state is not evidence, a driver-published property is.

        :data:`ALIVE_PROPERTY` is defined only once the driver's ``Connect()``
        succeeded, i.e. once both motor controllers replied. Its *widgets*
        get their names only once the property tree has finished streaming,
        so a named widget is checked rather than the bare vector, which can
        be a placeholder (journal S37/S38 -- and the ``KeyError: '6x'`` that
        exposed this on a dead mount).

        Raises:
            TimeoutError: propagated from :meth:`_await_widgets`, leaving the
                caller to publish ``error`` (boot) or ``disconnected``
                (reconnect, so the supervisor keeps retrying).
        """
        await self._await_widgets(
            lambda dev: dev.getSwitch(self.ALIVE_PROPERTY),
            widgets=(self.ALIVE_WIDGET,),
            context=self.ALIVE_PROPERTY,
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
            set_switch_one_of_many(rate_vec, f"{rate}x")
            await asyncio.to_thread(self._client.sendNewProperty, rate_vec)

            # 2. Start motion on the correct axis.
            motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
            on_elem, off_elem = self._AXIS_DIR_TO_ELEMENT[(axis, direction)]
            motion_vec = self._device.getSwitch(motion_name)
            if motion_vec is None:
                raise RuntimeError(f"{motion_name} property not found")
            find_widget(motion_vec, on_elem).setState(SWITCH_ON)
            find_widget(motion_vec, off_elem).setState(SWITCH_OFF)
            await asyncio.to_thread(self._client.sendNewProperty, motion_vec)
        except Exception as exc:
            self._publish_error(exc, context="slew")
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
                find_widget(abort_vec, "ABORT").setState(SWITCH_ON)
                await asyncio.to_thread(self._client.sendNewProperty, abort_vec)
                self._active_slews = []
                self._goto_in_progress = False
                self._goto_target = None
            else:
                motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
                motion_vec = self._device.getSwitch(motion_name)
                if motion_vec is None:
                    raise RuntimeError(f"{motion_name} property not found")
                for elem in motion_vec:
                    elem.setState(SWITCH_OFF)
                await asyncio.to_thread(self._client.sendNewProperty, motion_vec)
                self._active_slews = [
                    s for s in self._active_slews if s["axis"] != axis
                ]
        except Exception as exc:
            self._publish_error(exc, context="stop_slew")
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
            time_vec = await self._await_widgets(
                lambda dev: dev.getText("TIME_UTC"),
                widgets=("UTC", "OFFSET"),
                context="TIME_UTC",
            )
            find_widget(time_vec, "UTC").setText(utc_naive.isoformat())
            find_widget(time_vec, "OFFSET").setText("0")
            await asyncio.to_thread(self._client.sendNewProperty, time_vec)
        except Exception as exc:
            self._publish_error(exc, context="set_time")

    async def set_location(self, lat: float, lon: float) -> None:
        if self._device is None:
            return
        try:
            geo = await self._await_widgets(
                lambda dev: dev.getNumber("GEOGRAPHIC_COORD"),
                widgets=("LAT", "LONG"),
                context="GEOGRAPHIC_COORD",
            )
            find_widget(geo, "LAT").setValue(float(lat))
            find_widget(geo, "LONG").setValue(float(lon))
            # ELEV left at its current value (set by user/setup later).
            await asyncio.to_thread(self._client.sendNewProperty, geo)
        except Exception as exc:
            self._publish_error(exc, context="set_location")

    # --- position courante -----------------------------------------------

    async def current_position(self) -> tuple[float, float]:
        """Read the mount's raw encoder angles as ``(az, alt)`` in degrees.

        Reads ``TELESCOPE_ENCODER_ANGLES`` (``AXIS_AZ`` 0–360, ``AXIS_ALT``
        −90–+90, read-only, refreshed by the driver every polling period)
        rather than ``HORIZONTAL_COORD``: the alignment wizard records the
        mount's **own** frame, which must not depend on whatever partial
        alignment model the driver happens to hold mid-wizard.

        Unlike the fire-and-forget commands in this adapter, this is a read
        whose caller needs a value — so a failure **raises** instead of
        silently no-op'ing, and also publishes ``error`` on the bus since
        unreadable encoders are a genuine fault, not an idle bench.

        Raises:
            SensorUnavailableError: mount not connected, or the driver never
                published usable encoder angles.
        """
        if self._device is None:
            raise SensorUnavailableError("mount not connected")
        try:
            angles = await self._await_widgets(
                lambda dev: dev.getNumber(ENCODER_ANGLES_PROPERTY),
                widgets=("AXIS_AZ", "AXIS_ALT"),
                context=ENCODER_ANGLES_PROPERTY,
            )
            az = float(find_widget(angles, "AXIS_AZ").getValue())
            alt = float(find_widget(angles, "AXIS_ALT").getValue())
        except Exception as exc:
            self._publish_error(exc, context="current_position")
            raise SensorUnavailableError(
                f"encoder angles unavailable: {exc}"
            ) from exc
        return az, alt

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
            find_widget(coord, "RA").setValue(float(ra_deg) / 15.0)
            find_widget(coord, "DEC").setValue(float(dec_deg))
            await asyncio.to_thread(self._client.sendNewProperty, coord)
        except Exception as exc:
            self._publish_error(exc, context="sync_radec")

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
            find_widget(coord, "RA").setValue(float(ra_deg) / 15.0)
            find_widget(coord, "DEC").setValue(float(dec_deg))
            await asyncio.to_thread(self._client.sendNewProperty, coord)
        except Exception as exc:
            self._publish_error(exc, context="goto_radec")
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

    _GOTO_DONE_STATES: frozenset[str] = frozenset({"Ok", "Idle"})

    def handle_property_update(self, prop: Any) -> None:
        """Réagit aux mises à jour de propriétés INDI (thread C++ → loop).

        Deux propriétés nous intéressent :

        * ``TELESCOPE_TRACK_STATE`` — miroir du suivi réel, à tout moment
          (cf. :meth:`_publish_track_state`) ;
        * ``EQUATORIAL_EOD_COORD`` — fin d'un GoTo : quand elle repasse à
          ``Ok``/``Idle`` alors qu'un goto était en cours, on publie
          ``ready`` + ``tracking=sidereal`` et on désarme le goto.

        Sync method : sûre à appeler depuis un callback (aucun await).
        """
        try:
            name = prop.getName()
        except Exception:
            return
        if name == "TELESCOPE_TRACK_STATE":
            self._publish_track_state(prop)
            return
        if not self._goto_in_progress:
            return
        if name != "EQUATORIAL_EOD_COORD":
            return
        if prop.getStateAsString() not in self._GOTO_DONE_STATES:
            return
        self._goto_in_progress = False
        self._goto_target = None
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"device": self._device_name},
                since=_now(),
            ),
        )
        self._publish_tracking("sidereal")

    def _publish_track_state(self, prop: Any) -> None:
        """Reflète sur le bus le suivi **réel** de la monture.

        La monture suit d'elle-même : ``INDI::Telescope`` réarme le suivi
        quand un mouvement manuel s'arrête, et c'est le comportement qu'on
        veut à l'oculaire — sans suivi, le champ d'étoiles défile et
        centrer une étoile devient impossible. Mais l'état ``tracking``
        n'était publié que depuis **nos** commandes : après un ``/stop``,
        l'app affichait ``off`` pendant que la monture suivait (journal
        S57). Un sous-système doit rapporter ce que fait la monture, pas ce
        qu'on lui a demandé en dernier — même principe que le garde-fou
        ``ready`` : un état de switch qu'on a poussé n'est pas une preuve.
        """
        try:
            track = as_switch_vector(prop)
            enabled = find_widget(track, "TRACK_ON").getState() == SWITCH_ON
        except Exception as exc:
            # Ne jamais avaler : c'est un AttributeError silencieux sur le
            # Property nu du callback qui a fait passer ce miroir pour
            # câblé alors qu'il ne se déclenchait pas (journal S57).
            logger.warning("tracking: TELESCOPE_TRACK_STATE illisible: %s", exc)
            return
        self._publish_tracking("sidereal" if enabled else "off")

    def _publish_tracking(self, state: str) -> None:
        """Publie ``tracking`` en filtrant les échos identiques du driver."""
        if state == self._last_track_state:
            return
        self._last_track_state = state
        self._bus.publish("tracking", SubsystemState(state=state, since=_now()))

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
            # Retour immédiat, sans attendre l'écho du driver ; celui-ci
            # passera ensuite par _publish_track_state et sera dédupliqué.
            self._publish_tracking("sidereal" if enabled else "off")
        except Exception as exc:
            self._publish_error(exc, context="set_tracking")

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
        return find_widget(cw, "INDI_ENABLED").getStateAsString() == "On"

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
            self._publish_error(exc, context="cordwrap_set_enabled")

    async def cordwrap_get_position(self) -> str:
        if self._device is None:
            return "N"
        cw_pos = self._device.getSwitch("CORDWRAP_POS")
        if cw_pos is None:
            return "N"
        for cardinal, elem_name in self._CORDWRAP_POS_ELEMENTS.items():
            if find_widget(cw_pos, elem_name).getStateAsString() == "On":
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
            self._publish_error(exc, context="cordwrap_set_position")

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
        return int(find_widget(bl, elem_name).getValue())

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
            find_widget(bl, elem_name).setValue(float(int(value)))
            await asyncio.to_thread(self._client.sendNewProperty, bl)
        except Exception as exc:
            self._publish_error(exc, context="set_backlash")
