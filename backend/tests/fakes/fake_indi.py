"""Programmable fake of ``PyIndi.BaseClient`` for adapter tests.

Reproduces just enough of the API used by ``MountIndiAdapter`` — and,
crucially, reproduces it **faithfully**. The real pyindi-client (SWIG
bindings) has three sharp edges that a naive fake hides, letting broken
adapter code pass tests while failing on hardware (see journal S37):

* Property vectors index by **int only**. ``vector["NAME"]`` raises
  ``TypeError`` — you must use ``vector.findWidgetByName("NAME")``.
* Switch widgets take an **integer state** (``ISS_ON == 1`` /
  ``ISS_OFF == 0``). ``setState("ON")`` is silently wrong (leaves it Off).
  Read back with ``getStateAsString()`` → ``"On"`` / ``"Off"``.
* Element names are the driver's real names (``1x``…``8x``, ``ABORT``, …).

This fake mirrors those edges so the test suite reflects reality.

* ``setServer(host, port)``, ``connectServer()`` (records the call,
  invokes ``serverConnected``).
* ``getDevice(name)`` (returns a ``FakeDevice`` from the pre-loaded set).
* ``sendNewProperty(prop)`` (records the call).
* ``watchDevice(name)`` (no-op).
* Subclasses override ``newDevice``, ``updateProperty``,
  ``serverConnected``, ``serverDisconnected`` — same as PyIndi.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

ISS_ON = 1
ISS_OFF = 0

_INT_ONLY = "PyIndi property vectors index by int only — use findWidgetByName"


def _as_int_state(value: str | int) -> int:
    """Normalise an initial-state literal (``"ON"``/``"OFF"`` or int)."""
    if isinstance(value, str):
        return ISS_ON if value.upper() == "ON" else ISS_OFF
    return int(value)


# --- numbers -------------------------------------------------------------


@dataclass
class FakeNumberElement:
    name: str
    value: float = 0.0

    def setValue(self, v: float) -> None:  # noqa: N802
        self.value = float(v)

    def getValue(self) -> float:  # noqa: N802
        return self.value

    def getName(self) -> str:  # noqa: N802
        return self.name


@dataclass
class FakeNumberVector:
    name: str
    elements: dict[str, FakeNumberElement] = field(default_factory=dict)
    state: str = "OK"

    def __iter__(self) -> Iterator[FakeNumberElement]:
        return iter(self.elements.values())

    def __getitem__(self, key: int) -> FakeNumberElement:
        if not isinstance(key, int):
            raise TypeError(_INT_ONLY)
        return list(self.elements.values())[key]

    def findWidgetByName(self, name: str) -> FakeNumberElement | None:  # noqa: N802,E501
        return self.elements.get(name)

    def getName(self) -> str:  # noqa: N802
        return self.name

    def getStateAsString(self) -> str:  # noqa: N802
        return self.state


# --- switches ------------------------------------------------------------


@dataclass
class FakeSwitchElement:
    name: str
    state: int = ISS_OFF  # ISS_ON (1) | ISS_OFF (0)

    def setState(self, s: int) -> None:  # noqa: N802
        if not isinstance(s, int):
            # Real SWIG binding silently ignores a str here (leaves it Off);
            # we raise so the mistake is caught loudly in tests.
            raise TypeError("switch setState expects int (ISS_ON/ISS_OFF)")
        self.state = s

    def getState(self) -> int:  # noqa: N802
        return self.state

    def getStateAsString(self) -> str:  # noqa: N802
        return "On" if self.state == ISS_ON else "Off"

    def getName(self) -> str:  # noqa: N802
        return self.name


@dataclass
class FakeSwitchVector:
    name: str
    elements: dict[str, FakeSwitchElement] = field(default_factory=dict)
    state: str = "OK"

    def __iter__(self) -> Iterator[FakeSwitchElement]:
        return iter(self.elements.values())

    def __getitem__(self, key: int) -> FakeSwitchElement:
        if not isinstance(key, int):
            raise TypeError(_INT_ONLY)
        return list(self.elements.values())[key]

    def findWidgetByName(self, name: str) -> FakeSwitchElement | None:  # noqa: N802,E501
        return self.elements.get(name)

    def getName(self) -> str:  # noqa: N802
        return self.name

    def getStateAsString(self) -> str:  # noqa: N802
        return self.state


# --- text ----------------------------------------------------------------


@dataclass
class FakeTextElement:
    name: str
    text: str = ""

    def setText(self, t: str) -> None:  # noqa: N802
        self.text = t

    def getText(self) -> str:  # noqa: N802
        return self.text

    def getName(self) -> str:  # noqa: N802
        return self.name


@dataclass
class FakeTextVector:
    name: str
    elements: dict[str, FakeTextElement] = field(default_factory=dict)
    state: str = "OK"

    def __iter__(self) -> Iterator[FakeTextElement]:
        return iter(self.elements.values())

    def __getitem__(self, key: int) -> FakeTextElement:
        if not isinstance(key, int):
            raise TypeError(_INT_ONLY)
        return list(self.elements.values())[key]

    def findWidgetByName(self, name: str) -> FakeTextElement | None:  # noqa: N802,E501
        return self.elements.get(name)

    def getName(self) -> str:  # noqa: N802
        return self.name


# --- device / client -----------------------------------------------------


class FakeDevice:
    def __init__(self, name: str) -> None:
        self._name = name
        self._numbers: dict[str, FakeNumberVector] = {}
        self._switches: dict[str, FakeSwitchVector] = {}
        self._texts: dict[str, FakeTextVector] = {}

    def getDeviceName(self) -> str:  # noqa: N802
        return self._name

    def getNumber(self, name: str) -> FakeNumberVector | None:  # noqa: N802
        return self._numbers.get(name)

    def getSwitch(self, name: str) -> FakeSwitchVector | None:  # noqa: N802
        return self._switches.get(name)

    def getText(self, name: str) -> FakeTextVector | None:  # noqa: N802
        return self._texts.get(name)

    def add_number(
        self, name: str, elements: dict[str, float]
    ) -> FakeNumberVector:
        vec = FakeNumberVector(
            name=name,
            elements={
                k: FakeNumberElement(name=k, value=v)
                for k, v in elements.items()
            },
        )
        self._numbers[name] = vec
        return vec

    def add_switch(
        self, name: str, elements: dict[str, str | int]
    ) -> FakeSwitchVector:
        vec = FakeSwitchVector(
            name=name,
            elements={
                k: FakeSwitchElement(name=k, state=_as_int_state(v))
                for k, v in elements.items()
            },
        )
        self._switches[name] = vec
        return vec

    def add_text(
        self, name: str, elements: dict[str, str]
    ) -> FakeTextVector:
        vec = FakeTextVector(
            name=name,
            elements={
                k: FakeTextElement(name=k, text=v) for k, v in elements.items()
            },
        )
        self._texts[name] = vec
        return vec


class FakeIndiClient:
    """Test stand-in for ``PyIndi.BaseClient``.

    Subclasses (or instances) can hook the four PyIndi callbacks the same
    way the real class does. ``sent_properties`` records every
    ``sendNewProperty`` call so tests can assert on the writes.
    """

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int | None = None
        self._devices: dict[str, FakeDevice] = {}
        self.sent_properties: list[Any] = []
        self.connected = False

    # --- API used by MountIndiAdapter -----------------------------------

    def setServer(self, host: str, port: int) -> None:  # noqa: N802
        self._host, self._port = host, int(port)

    def connectServer(self) -> bool:  # noqa: N802
        self.connected = True
        self.serverConnected()
        for dev in self._devices.values():
            self.newDevice(dev)
        return True

    def disconnectServer(self) -> bool:  # noqa: N802
        self.connected = False
        self.serverDisconnected(0)
        return True

    def getDevice(self, name: str) -> FakeDevice | None:  # noqa: N802
        return self._devices.get(name)

    def watchDevice(self, name: str) -> None:  # noqa: N802
        pass

    def sendNewProperty(self, prop: Any) -> None:  # noqa: N802
        self.sent_properties.append(prop)

    # --- callbacks (override in tests / subclasses) ---------------------

    def serverConnected(self) -> None:  # noqa: N802
        pass

    def serverDisconnected(self, code: int) -> None:  # noqa: N802
        pass

    def newDevice(self, dev: FakeDevice) -> None:  # noqa: N802
        pass

    def updateProperty(self, prop: Any) -> None:  # noqa: N802
        pass

    # --- test-only programming surface ---------------------------------

    def add_device(self, name: str) -> FakeDevice:
        dev = FakeDevice(name)
        self._devices[name] = dev
        return dev

    def simulate_disconnect(self, code: int = 1) -> None:
        self.connected = False
        self.serverDisconnected(code)

    def simulate_property_update(self, prop: Any) -> None:
        self.updateProperty(prop)
