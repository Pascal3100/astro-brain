"""Unit tests for the pure property helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from astro_brain.adapters._indi_property_helpers import (
    indi_state_string,
    set_number_values,
    set_switch_one_of_many,
)


@dataclass
class _FakeNumElement:
    name: str
    value: float = 0.0

    def setValue(self, v: float) -> None:  # noqa: N802 (PyIndi API name)
        self.value = float(v)

    def getValue(self) -> float:  # noqa: N802
        return self.value


class _FakeNumberVector:
    def __init__(self, elements: list[_FakeNumElement]) -> None:
        self._elements = {e.name: e for e in elements}

    def __getitem__(self, key: str | int) -> _FakeNumElement:
        if isinstance(key, int):
            return list(self._elements.values())[key]
        return self._elements[key]


def test_set_number_values_writes_each_named_element() -> None:
    vec = _FakeNumberVector(
        [_FakeNumElement("RA"), _FakeNumElement("DEC")]
    )
    set_number_values(vec, {"RA": 12.5, "DEC": -34.0})
    assert vec["RA"].getValue() == 12.5
    assert vec["DEC"].getValue() == -34.0


def test_set_number_values_raises_on_unknown_element() -> None:
    vec = _FakeNumberVector([_FakeNumElement("RA")])
    with pytest.raises(KeyError):
        set_number_values(vec, {"FOO": 1.0})


@dataclass
class _FakeSwitchElement:
    name: str
    state: str = "OFF"  # "ON" | "OFF"

    def setState(self, s: str) -> None:  # noqa: N802
        self.state = s

    def getState(self) -> str:  # noqa: N802
        return self.state


class _FakeSwitchVector:
    def __init__(self, elements: list[_FakeSwitchElement]) -> None:
        self._elements = {e.name: e for e in elements}

    def __iter__(self):
        return iter(self._elements.values())

    def __getitem__(self, key: str) -> _FakeSwitchElement:
        return self._elements[key]


def test_set_switch_one_of_many_turns_target_on_others_off() -> None:
    vec = _FakeSwitchVector(
        [
            _FakeSwitchElement("SLEW", state="ON"),
            _FakeSwitchElement("TRACK"),
            _FakeSwitchElement("SYNC"),
        ]
    )
    set_switch_one_of_many(vec, "SYNC")
    assert vec["SLEW"].getState() == "OFF"
    assert vec["TRACK"].getState() == "OFF"
    assert vec["SYNC"].getState() == "ON"


class _FakeVecWithState:
    def __init__(self, state: str) -> None:
        self._state = state

    def getStateAsString(self) -> str:  # noqa: N802
        return self._state


def test_indi_state_string_returns_vector_state() -> None:
    assert indi_state_string(_FakeVecWithState("OK")) == "OK"
    assert indi_state_string(_FakeVecWithState("BUSY")) == "BUSY"
