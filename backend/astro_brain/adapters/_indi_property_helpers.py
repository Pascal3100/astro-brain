"""Pure helpers for manipulating PyIndi property vectors.

These functions target the **real** pyindi-client (SWIG) API, which has
two traps a naive helper falls into (see journal S37):

* Elements are reached with ``vector.findWidgetByName("NAME")`` — string
  subscript (``vector["NAME"]``) raises ``TypeError`` on real vectors.
* Switch state is an **integer** (:data:`SWITCH_ON` / :data:`SWITCH_OFF`,
  the ``ISState`` enum values). ``setState("ON")`` is silently ignored.

They never perform I/O, never call ``sendNewProperty``, and are tested
with a faithful fake — no ``libindi`` dependency on the workstation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# ISState enum values (PyIndi.ISS_ON / ISS_OFF). Hard-coded so this module
# stays importable on the workstation (no PyIndi). Verified on-device: the
# SWIG binding accepts the plain ints and rejects the "ON"/"OFF" strings.
SWITCH_ON = 1
SWITCH_OFF = 0


def find_widget(vector: Any, name: str) -> Any:
    """Return the widget named ``name`` from a PyIndi property vector.

    Uses ``findWidgetByName`` — the real accessor. String subscripting a
    real vector raises ``TypeError`` (int index only), which is exactly
    the trap this indirection removes.

    Raises:
        KeyError: if no widget with that name exists.
    """
    widget = vector.findWidgetByName(name)
    if widget is None:
        raise KeyError(name)
    return widget


def set_number_values(vector: Any, values: Mapping[str, float]) -> None:
    """Write each ``name -> value`` pair onto the vector's elements.

    Raises:
        KeyError: if any name is absent from the vector.
    """
    for name, value in values.items():
        find_widget(vector, name).setValue(float(value))


def set_switch_one_of_many(vector: Any, on_name: str) -> None:
    """Set ``on_name`` to ON, every other element to OFF (1-of-many rule).

    Raises:
        KeyError: if ``on_name`` is absent from the vector.
    """
    found = False
    for element in vector:
        if element.getName() == on_name:
            element.setState(SWITCH_ON)
            found = True
        else:
            element.setState(SWITCH_OFF)
    if not found:
        raise KeyError(on_name)


def indi_state_string(vector: Any) -> str:
    """Return ``"OK" | "BUSY" | "IDLE" | "ALERT"`` for the vector."""
    return vector.getStateAsString()
