"""Unit tests for the pure property helpers.

The local fakes mirror the real pyindi-client API: elements are reached
via ``findWidgetByName`` (not ``vector[name]``) and switch state is an
integer (``1`` = ON, ``0`` = OFF), read back with ``getStateAsString``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from astro_brain.adapters._indi_property_helpers import (
    as_switch_vector,
    set_switch_one_of_many,
)


@dataclass
class _FakeSwitchElement:
    name: str
    state: int = 0  # 1 = ON, 0 = OFF (ISState semantics)

    def setState(self, s: int) -> None:  # noqa: N802
        if not isinstance(s, int):
            raise TypeError("switch setState expects int")
        self.state = s

    def getStateAsString(self) -> str:  # noqa: N802
        return "On" if self.state == 1 else "Off"

    def getName(self) -> str:  # noqa: N802
        return self.name


class _FakeSwitchVector:
    def __init__(self, elements: list[_FakeSwitchElement]) -> None:
        self._elements = {e.name: e for e in elements}

    def __iter__(self):
        return iter(self._elements.values())

    def findWidgetByName(self, name: str) -> _FakeSwitchElement | None:  # noqa: N802,E501
        return self._elements.get(name)


def test_set_switch_one_of_many_turns_target_on_others_off() -> None:
    vec = _FakeSwitchVector(
        [
            _FakeSwitchElement("SLEW", state=1),
            _FakeSwitchElement("TRACK"),
            _FakeSwitchElement("SYNC"),
        ]
    )
    set_switch_one_of_many(vec, "SYNC")
    assert vec.findWidgetByName("SLEW").getStateAsString() == "Off"
    assert vec.findWidgetByName("TRACK").getStateAsString() == "Off"
    assert vec.findWidgetByName("SYNC").getStateAsString() == "On"


def test_set_switch_one_of_many_raises_on_unknown_element() -> None:
    vec = _FakeSwitchVector([_FakeSwitchElement("SLEW")])
    with pytest.raises(KeyError):
        set_switch_one_of_many(vec, "NOPE")


# --- as_switch_vector ----------------------------------------------------


class _BareProperty:
    """Ce que ``updateProperty()`` livre réellement : pas de widgets.

    Le ``INDI::Property`` du callback expose le nom et l'état mais pas
    ``findWidgetByName`` — vérifié sur le Pi (journal S57).
    """

    def getName(self) -> str:  # noqa: N802
        return "TELESCOPE_TRACK_STATE"


def test_as_switch_vector_leaves_a_typed_vector_untouched() -> None:
    vec = _FakeSwitchVector(
        [_FakeSwitchElement("TRACK_ON", 1), _FakeSwitchElement("TRACK_OFF", 0)]
    )
    assert as_switch_vector(vec) is vec


def test_as_switch_vector_casts_a_bare_callback_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans le cast, le miroir de suivi ne se déclenche jamais."""
    import sys
    import types

    bare = _BareProperty()
    typed = _FakeSwitchVector([_FakeSwitchElement("TRACK_ON", 1)])
    fake_pyindi = types.ModuleType("PyIndi")
    fake_pyindi.PropertySwitch = lambda prop: typed  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "PyIndi", fake_pyindi)

    assert as_switch_vector(bare) is typed
