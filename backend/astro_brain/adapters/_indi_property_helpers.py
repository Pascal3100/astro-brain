"""Pure helpers for manipulating PyIndi property vectors.

These functions accept any object that quacks like a PyIndi property
(``vec[name].setValue(...)``, ``vec[name].getValue()``,
``vec.getStateAsString()``). They never perform I/O, never call
``sendNewProperty``, and are tested with a fake property vector — no
``libindi`` dependency required on the workstation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def set_number_values(vector: Any, values: Mapping[str, float]) -> None:
    """Write each ``name -> value`` pair onto the vector's elements.

    Raises:
        KeyError: if any name is absent from the vector.
    """
    for name, value in values.items():
        element = vector[name]  # KeyError propagates
        element.setValue(float(value))


def set_switch_one_of_many(vector: Any, on_name: str) -> None:
    """Set ``on_name`` to ON, every other element to OFF (1-of-many rule)."""
    found = False
    for element in vector:
        if element.name == on_name:
            element.setState("ON")
            found = True
        else:
            element.setState("OFF")
    if not found:
        raise KeyError(on_name)


def indi_state_string(vector: Any) -> str:
    """Return ``"OK" | "BUSY" | "IDLE" | "ALERT"`` for the vector."""
    return vector.getStateAsString()
