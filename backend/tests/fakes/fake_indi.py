"""Programmable fake of ``PyIndi.BaseClient`` for adapter tests.

Reproduces just enough of the API used by ``MountIndiAdapter``:

* ``setServer(host, port)``, ``connectServer()`` (records the call,
  invokes ``serverConnected``).
* ``getDevice(name)`` (returns a ``FakeDevice`` from the pre-loaded set).
* ``sendNewProperty(prop)`` (records the call, optionally triggers a
  state transition queued by the test author).
* ``watchDevice(name)`` (no-op).
* Subclasses override ``newDevice``, ``updateProperty``,
  ``serverConnected``, ``serverDisconnected`` — same as PyIndi.

Tests pre-load fake devices/properties via :meth:`add_device` and
:meth:`FakeDevice.add_number`/:meth:`add_switch`, then drive transitions
via :meth:`FakeIndiClient.simulate_disconnect` etc.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeNumberElement:
    name: str
    value: float = 0.0

    def setValue(self, v: float) -> None:  # noqa: N802
        self.value = float(v)

    def getValue(self) -> float:  # noqa: N802
        return self.value


@dataclass
class FakeNumberVector:
    name: str
    elements: dict[str, FakeNumberElement] = field(default_factory=dict)
    state: str = "OK"

    def __getitem__(self, key: str | int) -> FakeNumberElement:
        if isinstance(key, int):
            return list(self.elements.values())[key]
        return self.elements[key]

    def getName(self) -> str:  # noqa: N802
        return self.name

    def getStateAsString(self) -> str:  # noqa: N802
        return self.state


@dataclass
class FakeSwitchElement:
    name: str
    state: str = "OFF"  # "ON" | "OFF"

    def setState(self, s: str) -> None:  # noqa: N802
        self.state = s

    def getState(self) -> str:  # noqa: N802
        return self.state


@dataclass
class FakeSwitchVector:
    name: str
    elements: dict[str, FakeSwitchElement] = field(default_factory=dict)
    state: str = "OK"

    def __iter__(self) -> Iterator[FakeSwitchElement]:
        return iter(self.elements.values())

    def __getitem__(self, key: str) -> FakeSwitchElement:
        return self.elements[key]

    def getName(self) -> str:  # noqa: N802
        return self.name

    def getStateAsString(self) -> str:  # noqa: N802
        return self.state


@dataclass
class FakeTextElement:
    name: str
    text: str = ""

    def setText(self, t: str) -> None:  # noqa: N802
        self.text = t

    def getText(self) -> str:  # noqa: N802
        return self.text


@dataclass
class FakeTextVector:
    name: str
    elements: dict[str, FakeTextElement] = field(default_factory=dict)
    state: str = "OK"

    def __getitem__(self, key: str) -> FakeTextElement:
        return self.elements[key]

    def getName(self) -> str:  # noqa: N802
        return self.name


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
            elements={k: FakeNumberElement(name=k, value=v) for k, v in elements.items()},
        )
        self._numbers[name] = vec
        return vec

    def add_switch(
        self, name: str, elements: dict[str, str]
    ) -> FakeSwitchVector:
        vec = FakeSwitchVector(
            name=name,
            elements={k: FakeSwitchElement(name=k, state=v) for k, v in elements.items()},
        )
        self._switches[name] = vec
        return vec

    def add_text(
        self, name: str, elements: dict[str, str]
    ) -> FakeTextVector:
        vec = FakeTextVector(
            name=name,
            elements={k: FakeTextElement(name=k, text=v) for k, v in elements.items()},
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
