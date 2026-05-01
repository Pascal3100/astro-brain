# Mount INDI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer `nexstarpy` par la stack INDI (`indiserver` + driver `indi_celestron_aux` + `pyindi-client`) en gardant l'interface `MountService`/`TrackingService` strictement identique côté FastAPI, étendre le driver upstream pour exposer le backlash 4-valeurs, et déployer le tout sur le Pi.

**Architecture:** Un nouvel adapter `MountIndiAdapter` remplace `NexStarMountAdapter`. Il sous-classe `PyIndi.BaseClient`, traduit chaque méthode du protocole en push de property INDI (`TELESCOPE_MOTION_NS`, `TELESCOPE_TRACK_STATE`, etc.), et publie sur le `StateBus` exactement comme avant. Un fake `FakeIndiClient` permet les tests workstation sans `libindi`. Le driver `indi_celestron_aux` est patché upstream pour ajouter une property `MOUNT_AXIS_BACKLASH` (Number RW × 4) câblée aux opcodes AUX `MC_*_BACKLASH` (0x10/0x11/0x40/0x41). `indiserver` tourne en service systemd avant `astro-brain.service`.

**Tech Stack:** Python 3.13, FastAPI, `pyindi-client` (binding SWIG officiel sur `libindi`), `indi_celestron_aux` C++ (BETA, `indi-3rdparty`), systemd, `uv`, pytest, ruff. Liaison physique : HC RJ12 → dongle CP2102 5V → `/dev/ttyUSB0` (NexStar 9600 baud, AUX en pass-through `'P'`).

**Scope du plan :**
- ✅ Parité v0.1 (slew, stop, tracking, set_time, set_location, watchdog) sur INDI.
- ✅ Cordwrap (read/write enabled + position 4 cardinaux).
- ✅ Patch driver C++ + property `MOUNT_AXIS_BACKLASH` + adapter Python qui consomme.
- ✅ Service systemd `indiserver` + ordering avec `astro-brain.service`.
- ✅ Doc : `architecture.md`, `deployment.md`, `INTEGRATION_CHECKLIST.md` actualisés.
- ❌ **Hors scope** : sync/goto RA-Dec (v0.3), pulse-guide (v0.7), hibernate/wake, alt limits côté monture (`LIMIT_POS` reporté à v0.2 Setup à proprement parler — ce plan livre seulement la primitive d'accès si elle se fait gratuitement, pas l'écran).

---

## File Structure

### Créés

| Fichier | Responsabilité |
|---|---|
| `backend/astro_brain/adapters/indi_client.py` | Sous-classe de `PyIndi.BaseClient` qui pousse les events INDI vers une `asyncio.Queue` thread-safe (passerelle callback → asyncio). |
| `backend/astro_brain/adapters/mount_indi_adapter.py` | Implémente `MountService` + `TrackingService` au-dessus d'`indi_client.py`. Traduit les méthodes haut-niveau en push de properties + publication bus. |
| `backend/astro_brain/adapters/_indi_property_helpers.py` | Helpers purs (`set_number`, `toggle_switch`, `wait_state`) — sans état, testables sans réseau. |
| `backend/tests/test_indi_property_helpers.py` | Tests des helpers purs. |
| `backend/tests/fakes/__init__.py` | (vide, package marker) |
| `backend/tests/fakes/fake_indi.py` | Faux `PyIndi` module + `FakeIndiClient` programmable injecté dans `MountIndiAdapter` lors des tests. |
| `backend/tests/test_mount_indi_adapter.py` | Tests unitaires de l'adapter. |
| `backend/deploy/indiserver.service` | Unit systemd qui lance `indiserver -v indi_celestron_aux` au boot. |
| `backend/deploy/build-indi-celestronaux.sh` | Script reproductible : clone du fork patché, build `.deb`, install + apt-hold. |
| `docs/superpowers/plans/2026-05-01-driver-patch-backlash.md` | (référencé) procédure C++ détaillée pour le patch driver — vit dans ce plan, pas dans un fichier séparé (cf. Task 12). |

### Modifiés

| Fichier | Changement |
|---|---|
| `backend/pyproject.toml` | `nexstarpy` out, `pyindi-client>=2.0` in (extra `hardware`). |
| `backend/astro_brain/app.py:42-56` | Remplacer `NexStarMountAdapter(bus)` par `MountIndiAdapter(bus)`. |
| `backend/astro_brain/adapters/nexstar_adapter.py` | **Supprimé** (legacy). |
| `backend/astro_brain/services/fakes.py:22-91` | `FakeMount` étendu avec `cordwrap_*` + `get_backlash`/`set_backlash` (no-op + valeur en mémoire) pour symétrie. |
| `backend/astro_brain/services/interfaces.py:21-37` | `MountService` étendu avec `get_backlash`/`set_backlash`/`cordwrap_*` (déclarations Protocol). |
| `backend/deploy/astro-brain.service:1-22` | `Requires=indiserver.service` + `After=indiserver.service`. |
| `backend/deploy/install.sh` | Installer aussi `indiserver.service`. |
| `backend/deploy/INTEGRATION_CHECKLIST.md` | Section 0 enrichie (apt deps INDI), section 3 Mount ré-écrite pour INDI, ajout de sections backlash + cordwrap. |
| `docs/technical/architecture.md` | Diagramme + texte mis à jour pour faire apparaître `indiserver`. |
| `docs/technical/deployment.md` | Apt deps INDI + procédure de build local du driver patché. |
| `docs/project/journal.md` | Entrée de session 2026-05-01. |

### Patch upstream (séparé, fork local le temps du merge)

Patches dans le repo cloné `indilib/indi-3rdparty`, sous-dir `indi-celestronaux/` :
- `auxproto.h` : 4 enum values dans `AUXCommands`.
- `celestronaux.h` : déclarations `MOUNT_AXIS_BACKLASH` + méthodes.
- `celestronaux.cpp` : `IUFillNumber` × 4, `defineProperty`, `getBacklash`/`setBacklash`, override `ISNewNumber`, hook dans `Handshake()`.

---

## Task 0 : Préparation — branche, baseline tests, archive nexstar

**Files:**
- Run only

- [ ] **Step 1 : Vérifier l'état git, créer la branche**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git status
git checkout -b feat/mount-indi
```

Expected: working tree clean (ou seulement les fichiers non-committed déjà connus), branche créée.

- [ ] **Step 2 : Baseline — tous les tests passent avant qu'on touche au code**

```bash
cd backend
uv run pytest -q
```

Expected: PASS (suite v0.1). Note le nombre de tests pour comparaison.

- [ ] **Step 3 : Commit baseline (no-op git)**

Pas de commit ici — on note juste le SHA de départ pour pouvoir comparer.

```bash
git rev-parse HEAD
```

---

## Task 1 : Helpers de manipulation de properties INDI (purs, testables)

Isole la logique « set un Number / toggle un Switch / lire un état » dans des fonctions pures qui prennent un objet property-like en argument. Pas d'I/O. Permet de tester la traduction métier → INDI sans connexion serveur.

**Files:**
- Create: `backend/astro_brain/adapters/_indi_property_helpers.py`
- Create: `backend/tests/test_indi_property_helpers.py`

- [ ] **Step 1 : Écrire le test pour `set_number_values`**

```python
# backend/tests/test_indi_property_helpers.py
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
```

- [ ] **Step 2 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py -v
```

Expected: FAIL with `ModuleNotFoundError: astro_brain.adapters._indi_property_helpers`.

- [ ] **Step 3 : Implémenter `set_number_values`**

```python
# backend/astro_brain/adapters/_indi_property_helpers.py
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
    raise NotImplementedError  # filled in next step


def indi_state_string(vector: Any) -> str:
    """Return ``"OK" | "BUSY" | "IDLE" | "ALERT"`` for the vector."""
    raise NotImplementedError  # filled in next step
```

- [ ] **Step 4 : Run tests — `set_number_values` passe**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py::test_set_number_values_writes_each_named_element \
              tests/test_indi_property_helpers.py::test_set_number_values_raises_on_unknown_element -v
```

Expected: 2 PASS.

- [ ] **Step 5 : Ajouter le test pour `set_switch_one_of_many`**

Append à `tests/test_indi_property_helpers.py` :

```python
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
```

- [ ] **Step 6 : Run failing test**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py::test_set_switch_one_of_many_turns_target_on_others_off -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 7 : Implémenter `set_switch_one_of_many`**

Remplacer le `raise NotImplementedError` dans `_indi_property_helpers.py` :

```python
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
```

- [ ] **Step 8 : Run tests**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py -v
```

Expected: 3 PASS.

- [ ] **Step 9 : Ajouter le test pour `indi_state_string`**

Append à `tests/test_indi_property_helpers.py` :

```python
class _FakeVecWithState:
    def __init__(self, state: str) -> None:
        self._state = state

    def getStateAsString(self) -> str:  # noqa: N802
        return self._state


def test_indi_state_string_returns_vector_state() -> None:
    assert indi_state_string(_FakeVecWithState("OK")) == "OK"
    assert indi_state_string(_FakeVecWithState("BUSY")) == "BUSY"
```

- [ ] **Step 10 : Run failing test**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py::test_indi_state_string_returns_vector_state -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 11 : Implémenter `indi_state_string`**

```python
def indi_state_string(vector: Any) -> str:
    """Return ``"OK" | "BUSY" | "IDLE" | "ALERT"`` for the vector."""
    return vector.getStateAsString()
```

- [ ] **Step 12 : Run all helper tests**

```bash
cd backend
uv run pytest tests/test_indi_property_helpers.py -v
```

Expected: 4 PASS.

- [ ] **Step 13 : Lint et commit**

```bash
cd backend
uv run ruff check .
git add astro_brain/adapters/_indi_property_helpers.py tests/test_indi_property_helpers.py
git commit -m "feat(backend): pure INDI property helpers (set_number, set_switch, state)"
```

Expected: ruff clean, commit créé.

---

## Task 2 : Fake INDI client pour tests workstation

Construit un faux `PyIndi.BaseClient` programmable. Permet d'écrire les tests de `MountIndiAdapter` sans `libindi`. Le fake exposera la même surface : `setServer`, `connectServer`, `getDevice`, `sendNewProperty`, et un `inject_property` pour pré-câbler des properties accessibles via `getNumber`/`getSwitch`.

**Files:**
- Create: `backend/tests/fakes/__init__.py`
- Create: `backend/tests/fakes/fake_indi.py`
- Modify: `backend/pyproject.toml` (whitelister `tests/fakes` comme package)

- [ ] **Step 1 : Créer le marqueur de package**

```python
# backend/tests/fakes/__init__.py
"""Test-only fakes for hardware adapters."""
```

- [ ] **Step 2 : Implémenter `FakeIndiClient`**

```python
# backend/tests/fakes/fake_indi.py
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
```

- [ ] **Step 3 : Whitelister `tests` (et `tests.fakes`) si nécessaire**

Vérifier dans `backend/pyproject.toml` la section `[tool.setuptools.packages.find]` : `where=["."]`, `include=["astro_brain*"]`. `tests/` n'est pas packagé — c'est OK, les tests `import` se font via le `pythonpath` automatique de pytest depuis `testpaths = ["tests"]`.

Vérifier qu'on peut importer le fake :

```bash
cd backend
uv run python -c "from tests.fakes.fake_indi import FakeIndiClient; print(FakeIndiClient())"
```

Expected: une ligne `<tests.fakes.fake_indi.FakeIndiClient object at 0x...>`.

Si ça échoue avec `ModuleNotFoundError: tests`, ajouter dans `pyproject.toml` sous `[tool.pytest.ini_options]` la clé `pythonpath = ["."]` :

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

Puis re-tester la commande ci-dessus.

- [ ] **Step 4 : Smoke test du fake**

```bash
cd backend
uv run python - <<'PY'
from tests.fakes.fake_indi import FakeIndiClient

c = FakeIndiClient()
dev = c.add_device("Celestron AUX")
dev.add_number("EQUATORIAL_EOD_COORD", {"RA": 0.0, "DEC": 0.0})
sw = dev.add_switch("ON_COORD_SET", {"SLEW": "ON", "TRACK": "OFF", "SYNC": "OFF"})
c.connectServer()
assert c.connected
n = dev.getNumber("EQUATORIAL_EOD_COORD")
n["RA"].setValue(12.0)
c.sendNewProperty(n)
assert c.sent_properties[0]["RA"].getValue() == 12.0
print("fake ok")
PY
```

Expected: `fake ok`.

- [ ] **Step 5 : Commit**

```bash
git add backend/tests/fakes/ backend/pyproject.toml
git commit -m "test(backend): programmable FakeIndiClient for adapter tests"
```

Expected: commit créé.

---

## Task 3 : `MountIndiAdapter` — squelette + start/stop

Crée la classe avec le constructeur, `start()`/`stop()`, et la publication initiale du subsystem `mount` (`connecting` → `ready`) + amorce du subsystem `tracking` (`off`). L'I/O réel arrive aux Tasks suivantes ; ici on met juste l'ossature et on injecte le client INDI par DI pour pouvoir tester avec `FakeIndiClient`.

**Files:**
- Create: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Create: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Écrire les tests start/stop**

```python
# backend/tests/test_mount_indi_adapter.py
"""Tests for MountIndiAdapter (start/stop, slew, tracking, watchdog)."""

from __future__ import annotations

import pytest

from astro_brain.adapters.mount_indi_adapter import (
    INDI_DEVICE_NAME,
    MountIndiAdapter,
)
from astro_brain.bus import StateBus
from tests.fakes.fake_indi import FakeIndiClient


def _seed_mount_device(client: FakeIndiClient) -> None:
    """Pre-load the fake with the properties MountIndiAdapter expects."""
    dev = client.add_device(INDI_DEVICE_NAME)
    dev.add_switch(
        "CONNECTION", {"CONNECT": "OFF", "DISCONNECT": "ON"}
    )
    dev.add_text("DEVICE_PORT", {"PORT": ""})
    dev.add_switch(
        "CONNECTION_MODE", {"CONNECTION_SERIAL": "ON", "CONNECTION_TCP": "OFF"}
    )


@pytest.mark.asyncio
async def test_start_publishes_connecting_then_ready_when_device_arrives() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)

    await adapter.start()

    full = bus.get_full_state()
    assert full.subsystems["mount"].state == "ready"
    assert full.subsystems["tracking"].state == "off"


@pytest.mark.asyncio
async def test_start_publishes_error_when_connect_fails() -> None:
    bus = StateBus()

    class _BadClient(FakeIndiClient):
        def connectServer(self) -> bool:  # noqa: N802
            raise RuntimeError("boom")

    adapter = MountIndiAdapter(bus, client=_BadClient())
    await adapter.start()

    state = bus.get_full_state().subsystems["mount"]
    assert state.state == "error"
    assert "boom" in (state.message or "")


@pytest.mark.asyncio
async def test_stop_publishes_disconnected() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.stop()

    assert bus.get_full_state().subsystems["mount"].state == "disconnected"
    assert client.connected is False
```

- [ ] **Step 2 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: collection error / `ModuleNotFoundError: astro_brain.adapters.mount_indi_adapter`.

- [ ] **Step 3 : Squelette de l'adapter**

```python
# backend/astro_brain/adapters/mount_indi_adapter.py
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
from datetime import datetime, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
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
    return datetime.now(timezone.utc)


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
                from astro_brain.adapters.indi_client import (
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
```

- [ ] **Step 4 : Run tests — start/stop passent**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 3 PASS.

- [ ] **Step 5 : Lint**

```bash
cd backend
uv run ruff check astro_brain/adapters/mount_indi_adapter.py tests/test_mount_indi_adapter.py
```

Expected: clean.

- [ ] **Step 6 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter skeleton (start/stop, device discovery)"
```

---

## Task 4 : `MountIndiAdapter` — slew + stop_slew

Mappe `slew(axis, direction, rate)` sur `TELESCOPE_SLEW_RATE` (selector 1OFMANY) + `TELESCOPE_MOTION_NS` ou `TELESCOPE_MOTION_WE`, et `stop_slew(axis|None)` sur la même property en OFF (ou `TELESCOPE_ABORT_MOTION` quand aucun axe spécifié).

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Ajouter le test slew (axe ALT, direction +, rate 4)**

Append à `backend/tests/test_mount_indi_adapter.py` :

```python
def _seed_motion_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "TELESCOPE_MOTION_NS", {"MOTION_NORTH": "OFF", "MOTION_SOUTH": "OFF"}
    )
    dev.add_switch(
        "TELESCOPE_MOTION_WE", {"MOTION_WEST": "OFF", "MOTION_EAST": "OFF"}
    )
    dev.add_switch(
        "TELESCOPE_SLEW_RATE",
        {f"SLEW_RATE_{i}": ("ON" if i == 1 else "OFF") for i in range(1, 9)},
    )
    dev.add_switch(
        "TELESCOPE_ABORT_MOTION", {"ABORT_MOTION": "OFF"}
    )


@pytest.mark.asyncio
async def test_slew_alt_plus_rate4_pushes_slew_rate_then_motion_north() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.slew("alt", "+", 4)

    dev = client.getDevice(INDI_DEVICE_NAME)
    rate_vec = dev.getSwitch("TELESCOPE_SLEW_RATE")
    motion_ns = dev.getSwitch("TELESCOPE_MOTION_NS")
    assert rate_vec["SLEW_RATE_4"].getState() == "ON"
    assert rate_vec["SLEW_RATE_1"].getState() == "OFF"
    assert motion_ns["MOTION_NORTH"].getState() == "ON"
    assert motion_ns["MOTION_SOUTH"].getState() == "OFF"
    # Two writes were sent: rate first, motion second
    sent_names = [p.getName() for p in client.sent_properties]
    assert sent_names == ["TELESCOPE_SLEW_RATE", "TELESCOPE_MOTION_NS"]
    assert bus.get_full_state().subsystems["mount"].state == "moving"


@pytest.mark.asyncio
async def test_slew_az_minus_pushes_motion_east() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.slew("az", "-", 2)

    motion_we = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_MOTION_WE")
    assert motion_we["MOTION_EAST"].getState() == "ON"
    assert motion_we["MOTION_WEST"].getState() == "OFF"


@pytest.mark.asyncio
async def test_stop_slew_axis_alt_only_turns_motion_ns_off() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.slew("alt", "+", 4)

    await adapter.stop_slew("alt")

    motion_ns = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_MOTION_NS")
    assert motion_ns["MOTION_NORTH"].getState() == "OFF"
    assert motion_ns["MOTION_SOUTH"].getState() == "OFF"
    assert bus.get_full_state().subsystems["mount"].state == "ready"


@pytest.mark.asyncio
async def test_stop_slew_no_axis_uses_abort_motion() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_motion_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.slew("alt", "+", 4)
    await adapter.slew("az", "-", 4)

    await adapter.stop_slew(None)

    abort = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_ABORT_MOTION")
    assert abort["ABORT_MOTION"].getState() == "ON"
    assert bus.get_full_state().subsystems["mount"].state == "ready"
```

- [ ] **Step 2 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v -k "slew or stop_slew"
```

Expected: FAIL — méthodes `slew`, `stop_slew` absentes de l'adapter.

- [ ] **Step 3 : Implémenter `slew` et `stop_slew`**

Append au fichier `backend/astro_brain/adapters/mount_indi_adapter.py` (à l'intérieur de la classe `MountIndiAdapter`, après `_await_device`) :

```python
    # --- joystick / slew --------------------------------------------------

    _AXIS_TO_MOTION_VECTOR = {
        "alt": "TELESCOPE_MOTION_NS",
        "az": "TELESCOPE_MOTION_WE",
    }
    _AXIS_DIR_TO_ELEMENT = {
        ("alt", "+"): ("MOTION_NORTH", "MOTION_SOUTH"),
        ("alt", "-"): ("MOTION_SOUTH", "MOTION_NORTH"),
        ("az", "+"): ("MOTION_WEST", "MOTION_EAST"),
        ("az", "-"): ("MOTION_EAST", "MOTION_WEST"),
    }

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        if self._device is None:
            return
        # Replace any existing slew on the same axis (joystick semantics).
        self._active_slews = [s for s in self._active_slews if s["axis"] != axis]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )

        try:
            # 1. Push the slew rate first (1-of-many switch).
            from astro_brain.adapters._indi_property_helpers import (
                set_switch_one_of_many,
            )

            rate_vec = self._device.getSwitch("TELESCOPE_SLEW_RATE")
            if rate_vec is None:
                raise RuntimeError("TELESCOPE_SLEW_RATE property not found")
            set_switch_one_of_many(rate_vec, f"SLEW_RATE_{rate}")
            await asyncio.to_thread(self._client.sendNewProperty, rate_vec)

            # 2. Then start the motion on the right axis.
            motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
            on_elem, off_elem = self._AXIS_DIR_TO_ELEMENT[(axis, direction)]
            motion_vec = self._device.getSwitch(motion_name)
            if motion_vec is None:
                raise RuntimeError(f"{motion_name} property not found")
            motion_vec[on_elem].setState("ON")
            motion_vec[off_elem].setState("OFF")
            await asyncio.to_thread(self._client.sendNewProperty, motion_vec)
        except Exception as exc:
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
                    "active_slews": list(self._active_slews),
                },
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        if self._device is None:
            return
        try:
            if axis is None:
                # Belt-and-braces: ABORT covers anything still moving.
                abort_vec = self._device.getSwitch("TELESCOPE_ABORT_MOTION")
                if abort_vec is None:
                    raise RuntimeError(
                        "TELESCOPE_ABORT_MOTION property not found"
                    )
                abort_vec["ABORT_MOTION"].setState("ON")
                await asyncio.to_thread(
                    self._client.sendNewProperty, abort_vec
                )
                self._active_slews = []
            else:
                motion_name = self._AXIS_TO_MOTION_VECTOR[axis]
                motion_vec = self._device.getSwitch(motion_name)
                if motion_vec is None:
                    raise RuntimeError(f"{motion_name} property not found")
                for elem in motion_vec:
                    elem.setState("OFF")
                await asyncio.to_thread(
                    self._client.sendNewProperty, motion_vec
                )
                self._active_slews = [
                    s for s in self._active_slews if s["axis"] != axis
                ]
        except Exception as exc:
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
                        "active_slews": list(self._active_slews),
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
```

- [ ] **Step 4 : Run tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 7 PASS (3 existants + 4 nouveaux).

- [ ] **Step 5 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter slew/stop_slew via TELESCOPE_MOTION_*"
```

---

## Task 5 : `MountIndiAdapter` — set_time + set_location

`set_time(utc_iso)` → push `TIME_UTC` (Text). `set_location(lat, lon)` → push `GEOGRAPHIC_COORD` (Number).

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Ajouter les tests**

Append à `backend/tests/test_mount_indi_adapter.py` :

```python
def _seed_time_location_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_text("TIME_UTC", {"UTC": "", "OFFSET": "0"})
    dev.add_number(
        "GEOGRAPHIC_COORD", {"LAT": 0.0, "LONG": 0.0, "ELEV": 0.0}
    )


@pytest.mark.asyncio
async def test_set_time_pushes_utc_text() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_time_location_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_time("2026-05-01T18:30:00+00:00")

    dev = client.getDevice(INDI_DEVICE_NAME)
    time_vec = dev.getText("TIME_UTC")
    assert time_vec["UTC"].getText() == "2026-05-01T18:30:00"
    assert time_vec["OFFSET"].getText() == "0"


@pytest.mark.asyncio
async def test_set_location_pushes_geographic_coord() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_time_location_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_location(43.6043, 1.4437)

    dev = client.getDevice(INDI_DEVICE_NAME)
    geo = dev.getNumber("GEOGRAPHIC_COORD")
    assert geo["LAT"].getValue() == pytest.approx(43.6043)
    assert geo["LONG"].getValue() == pytest.approx(1.4437)
```

- [ ] **Step 2 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v -k "set_time or set_location"
```

Expected: FAIL — méthodes manquantes.

- [ ] **Step 3 : Implémenter dans `mount_indi_adapter.py`**

Append à la classe (après `stop_slew`) :

```python
    # --- time / location --------------------------------------------------

    async def set_time(self, utc_iso: str) -> None:
        if self._device is None:
            return
        try:
            dt = datetime.fromisoformat(utc_iso)
            # INDI TIME_UTC.UTC expects ISO without tzinfo (UTC implicit).
            utc_naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
            time_vec = self._device.getText("TIME_UTC")
            if time_vec is None:
                raise RuntimeError("TIME_UTC property not found")
            time_vec["UTC"].setText(utc_naive.isoformat())
            time_vec["OFFSET"].setText("0")
            await asyncio.to_thread(self._client.sendNewProperty, time_vec)
        except Exception as exc:
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
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
```

- [ ] **Step 4 : Run tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 9 PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter set_time/set_location via TIME_UTC/GEOGRAPHIC_COORD"
```

---

## Task 6 : `MountIndiAdapter` — set_tracking

`set_tracking(enabled)` → push `TELESCOPE_TRACK_STATE` (switch 1OFMANY `TRACK_ON`/`TRACK_OFF`) + publication `tracking` sur le bus.

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Ajouter les tests**

Append à `backend/tests/test_mount_indi_adapter.py` :

```python
def _seed_tracking_property(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "TELESCOPE_TRACK_STATE", {"TRACK_ON": "OFF", "TRACK_OFF": "ON"}
    )


@pytest.mark.asyncio
async def test_set_tracking_true_pushes_track_on_and_publishes_sidereal() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_tracking(True)

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    assert track["TRACK_ON"].getState() == "ON"
    assert track["TRACK_OFF"].getState() == "OFF"
    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"


@pytest.mark.asyncio
async def test_set_tracking_false_pushes_track_off_and_publishes_off() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_tracking_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.set_tracking(True)

    await adapter.set_tracking(False)

    track = client.getDevice(INDI_DEVICE_NAME).getSwitch("TELESCOPE_TRACK_STATE")
    assert track["TRACK_OFF"].getState() == "ON"
    assert track["TRACK_ON"].getState() == "OFF"
    assert bus.get_full_state().subsystems["tracking"].state == "off"
```

- [ ] **Step 2 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v -k "tracking"
```

Expected: FAIL — `set_tracking` manquant.

- [ ] **Step 3 : Implémenter dans la classe**

Append après `set_location` :

```python
    # --- tracking (TrackingService surface) -------------------------------

    async def set_tracking(self, enabled: bool) -> None:
        if self._device is None:
            return
        try:
            from astro_brain.adapters._indi_property_helpers import (
                set_switch_one_of_many,
            )

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
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
```

- [ ] **Step 4 : Run tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 11 PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter set_tracking via TELESCOPE_TRACK_STATE"
```

---

## Task 7 : Cordwrap (read/write enabled + position 4 cardinaux)

`indi_celestron_aux` expose nativement `CORDWRAP` (switch on/off) et `CORDWRAP_POS` (switch 4 cardinaux N/E/S/W). On expose 4 méthodes à l'adapter : `cordwrap_get_enabled`, `cordwrap_set_enabled`, `cordwrap_get_position`, `cordwrap_set_position`. Pas besoin de patch driver.

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/astro_brain/services/interfaces.py`
- Modify: `backend/astro_brain/services/fakes.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Étendre le Protocol `MountService`**

Modifier `backend/astro_brain/services/interfaces.py` — ajouter à la classe `MountService`, après `set_location` :

```python
    async def cordwrap_get_enabled(self) -> bool: ...
    async def cordwrap_set_enabled(self, enabled: bool) -> None: ...
    async def cordwrap_get_position(self) -> str: ...
    async def cordwrap_set_position(self, position: str) -> None: ...
```

`position` est l'un de `"N"|"E"|"S"|"W"`.

- [ ] **Step 2 : Étendre `FakeMount` pour rester compatible**

Dans `backend/astro_brain/services/fakes.py`, à la fin de la classe `FakeMount` (avant `class FakeTracking`) :

```python
    # --- cordwrap (in-memory toggles) -----------------------------------

    _cordwrap_enabled: bool = False
    _cordwrap_position: str = "N"

    async def cordwrap_get_enabled(self) -> bool:
        return self._cordwrap_enabled

    async def cordwrap_set_enabled(self, enabled: bool) -> None:
        self._cordwrap_enabled = bool(enabled)

    async def cordwrap_get_position(self) -> str:
        return self._cordwrap_position

    async def cordwrap_set_position(self, position: str) -> None:
        if position not in {"N", "E", "S", "W"}:
            raise ValueError(f"invalid cordwrap position: {position!r}")
        self._cordwrap_position = position
```

- [ ] **Step 3 : Ajouter les tests pour l'adapter**

Append à `backend/tests/test_mount_indi_adapter.py` :

```python
def _seed_cordwrap_properties(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_switch(
        "CORDWRAP", {"INDI_ENABLED": "OFF", "INDI_DISABLED": "ON"}
    )
    dev.add_switch(
        "CORDWRAP_POS",
        {"CORDWRAP_N": "ON", "CORDWRAP_E": "OFF", "CORDWRAP_S": "OFF", "CORDWRAP_W": "OFF"},
    )


@pytest.mark.asyncio
async def test_cordwrap_set_enabled_true_toggles_indi_enabled_on() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.cordwrap_set_enabled(True)

    cw = client.getDevice(INDI_DEVICE_NAME).getSwitch("CORDWRAP")
    assert cw["INDI_ENABLED"].getState() == "ON"
    assert cw["INDI_DISABLED"].getState() == "OFF"


@pytest.mark.asyncio
async def test_cordwrap_get_enabled_reads_current_state() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    assert await adapter.cordwrap_get_enabled() is False
    await adapter.cordwrap_set_enabled(True)
    assert await adapter.cordwrap_get_enabled() is True


@pytest.mark.asyncio
async def test_cordwrap_set_position_east() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.cordwrap_set_position("E")

    cw_pos = client.getDevice(INDI_DEVICE_NAME).getSwitch("CORDWRAP_POS")
    assert cw_pos["CORDWRAP_E"].getState() == "ON"
    assert cw_pos["CORDWRAP_N"].getState() == "OFF"


@pytest.mark.asyncio
async def test_cordwrap_set_position_invalid_raises() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    with pytest.raises(ValueError):
        await adapter.cordwrap_set_position("Z")


@pytest.mark.asyncio
async def test_cordwrap_get_position_reads_active_cardinal() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_cordwrap_properties(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    await adapter.cordwrap_set_position("S")
    assert await adapter.cordwrap_get_position() == "S"
```

- [ ] **Step 4 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v -k "cordwrap"
```

Expected: FAIL — méthodes manquantes.

- [ ] **Step 5 : Implémenter dans `mount_indi_adapter.py`**

Append à la classe (après `set_tracking`) :

```python
    # --- cordwrap (AUX driver native) ------------------------------------

    _CORDWRAP_POS_ELEMENTS = {
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
            from astro_brain.adapters._indi_property_helpers import (
                set_switch_one_of_many,
            )

            cw = self._device.getSwitch("CORDWRAP")
            if cw is None:
                raise RuntimeError("CORDWRAP property not found")
            set_switch_one_of_many(
                cw, "INDI_ENABLED" if enabled else "INDI_DISABLED"
            )
            await asyncio.to_thread(self._client.sendNewProperty, cw)
        except Exception as exc:
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
            from astro_brain.adapters._indi_property_helpers import (
                set_switch_one_of_many,
            )

            cw_pos = self._device.getSwitch("CORDWRAP_POS")
            if cw_pos is None:
                raise RuntimeError("CORDWRAP_POS property not found")
            set_switch_one_of_many(
                cw_pos, self._CORDWRAP_POS_ELEMENTS[position]
            )
            await asyncio.to_thread(self._client.sendNewProperty, cw_pos)
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
```

- [ ] **Step 6 : Run all adapter tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 16 PASS.

- [ ] **Step 7 : Run full suite**

```bash
cd backend
uv run pytest -q
```

Expected: tous les tests passent (incluant les anciens via le fake étendu).

- [ ] **Step 8 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/astro_brain/services/interfaces.py backend/astro_brain/services/fakes.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter cordwrap (enabled + position 4 cardinaux)"
```

---

## Task 8 : Backlash — interface + Fake (driver patch viendra ensuite)

L'API Python du backlash s'écrit avant le patch C++ : on expose `get_backlash(axis, direction) -> int` et `set_backlash(axis, direction, value)` côté `MountService` Protocol + `FakeMount`. L'adapter INDI les implémente en lisant/écrivant la property `MOUNT_AXIS_BACKLASH` (à 4 éléments `AZ_POS`/`AZ_NEG`/`ALT_POS`/`ALT_NEG`). Tant que le driver upstream n'est pas patché, la property sera absente sur le hardware réel ; l'adapter renvoie alors `0` en lecture et logge une `RuntimeError("MOUNT_AXIS_BACKLASH not advertised by driver — patch required")` en écriture. Les tests utilisent le `FakeIndiClient` qui simule la property présente.

**Files:**
- Modify: `backend/astro_brain/services/interfaces.py`
- Modify: `backend/astro_brain/services/fakes.py`
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/tests/test_mount_indi_adapter.py`

- [ ] **Step 1 : Étendre le Protocol `MountService`**

Modifier `backend/astro_brain/services/interfaces.py` — ajouter à `MountService`, juste après les méthodes cordwrap :

```python
    async def get_backlash(self, axis: Axis, direction: Direction) -> int: ...
    async def set_backlash(
        self, axis: Axis, direction: Direction, value: int
    ) -> None: ...
```

- [ ] **Step 2 : Étendre `FakeMount`**

Dans `backend/astro_brain/services/fakes.py`, à la fin de `FakeMount` :

```python
    # --- backlash (in-memory 4-value table) -----------------------------

    _backlash_table: dict[tuple[str, str], int] = {  # noqa: RUF012
        ("alt", "+"): 0,
        ("alt", "-"): 0,
        ("az", "+"): 0,
        ("az", "-"): 0,
    }

    async def get_backlash(self, axis: Axis, direction: Direction) -> int:
        return self._backlash_table[(axis, direction)]

    async def set_backlash(
        self, axis: Axis, direction: Direction, value: int
    ) -> None:
        if not 0 <= int(value) <= 99:
            raise ValueError(f"backlash value out of range: {value}")
        self._backlash_table[(axis, direction)] = int(value)
```

- [ ] **Step 3 : Ajouter les tests pour l'adapter INDI**

Append à `backend/tests/test_mount_indi_adapter.py` :

```python
def _seed_backlash_property(client: FakeIndiClient) -> None:
    dev = client.getDevice(INDI_DEVICE_NAME)
    assert dev is not None
    dev.add_number(
        "MOUNT_AXIS_BACKLASH",
        {"AZ_POS": 0.0, "AZ_NEG": 0.0, "ALT_POS": 0.0, "ALT_NEG": 0.0},
    )


@pytest.mark.asyncio
async def test_get_backlash_reads_property_element() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    bl = client.getDevice(INDI_DEVICE_NAME).getNumber("MOUNT_AXIS_BACKLASH")
    bl["ALT_POS"].setValue(12.0)

    assert await adapter.get_backlash("alt", "+") == 12


@pytest.mark.asyncio
async def test_set_backlash_writes_property_element() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_backlash("az", "-", 25)

    bl = client.getDevice(INDI_DEVICE_NAME).getNumber("MOUNT_AXIS_BACKLASH")
    assert bl["AZ_NEG"].getValue() == 25.0


@pytest.mark.asyncio
async def test_set_backlash_value_out_of_range_raises() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    _seed_backlash_property(client)
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    with pytest.raises(ValueError):
        await adapter.set_backlash("alt", "+", 150)


@pytest.mark.asyncio
async def test_get_backlash_returns_zero_when_property_absent() -> None:
    """Driver not patched yet — property is absent. Don't crash, return 0."""
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    # Note: no backlash property seeded.
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()
    assert await adapter.get_backlash("alt", "+") == 0


@pytest.mark.asyncio
async def test_set_backlash_when_property_absent_publishes_error() -> None:
    bus = StateBus()
    client = FakeIndiClient()
    _seed_mount_device(client)
    # No backlash property — simulating an unpatched driver.
    adapter = MountIndiAdapter(bus, client=client)
    await adapter.start()

    await adapter.set_backlash("alt", "+", 5)

    assert bus.get_full_state().subsystems["mount"].state == "error"
```

- [ ] **Step 4 : Run failing tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v -k "backlash"
```

Expected: FAIL.

- [ ] **Step 5 : Implémenter dans `mount_indi_adapter.py`**

Append à la classe :

```python
    # --- backlash (driver patch required upstream) ----------------------

    _BACKLASH_ELEMENT = {
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
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
```

- [ ] **Step 6 : Run tests**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -v
```

Expected: 21 PASS.

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/astro_brain/services/interfaces.py backend/astro_brain/services/fakes.py backend/tests/test_mount_indi_adapter.py
git commit -m "feat(backend): MountIndiAdapter backlash 4-values (depends on driver patch)"
```

---

## Task 9 : Sous-classe réelle `AstroBrainIndiClient` (production seulement)

Crée la passerelle entre les callbacks synchrones de `PyIndi.BaseClient` et le bus asyncio. Conçue pour ne PAS être importée dans les tests (elle dépend de `PyIndi`, indisponible sur la workstation). Importée paresseusement par `MountIndiAdapter.start()` quand `client is None`.

**Files:**
- Create: `backend/astro_brain/adapters/indi_client.py`

- [ ] **Step 1 : Implémenter la sous-classe**

```python
# backend/astro_brain/adapters/indi_client.py
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
from datetime import datetime, timezone

import PyIndi  # type: ignore[import-not-found]

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
```

- [ ] **Step 2 : Vérifier que les tests existants passent toujours**

```bash
cd backend
uv run pytest tests/test_mount_indi_adapter.py -q
```

Expected: 21 PASS — l'adapter n'importe `indi_client` que dans la branche production (`if self._client is None`), jamais touchée par les tests.

- [ ] **Step 3 : Smoke test workstation — l'adapter reste importable**

```bash
cd backend
uv run python -c "from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter; print('ok')"
```

Expected: `ok`. (`indi_client.py` n'est pas chargé tant que `start()` n'est pas appelé sans `client` injecté.)

- [ ] **Step 4 : Commit**

```bash
git add backend/astro_brain/adapters/indi_client.py
git commit -m "feat(backend): AstroBrainIndiClient (PyIndi.BaseClient bridging to StateBus)"
```

---

## Task 10 : Wire l'adapter dans `app.py` + retirer `nexstarpy`

Remplace `NexStarMountAdapter(bus)` par `MountIndiAdapter(bus)`, supprime `nexstar_adapter.py`, met à jour `pyproject.toml` (drop `nexstarpy`, add `pyindi-client`).

**Files:**
- Modify: `backend/astro_brain/app.py`
- Delete: `backend/astro_brain/adapters/nexstar_adapter.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1 : Remplacer l'import + l'instanciation dans `app.py`**

Dans `backend/astro_brain/app.py:42-56`, remplacer le bloc `if use_hardware:` par :

```python
    if use_hardware:
        from astro_brain.adapters.gpsd_adapter import GpsdAdapter
        from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = MountIndiAdapter(bus)
        # The mount adapter also implements ``set_tracking`` — re-use it
        # as the tracking service so ``/tracking`` drives real hardware.
        return {
            "mount": mount,
            "gps": GpsdAdapter(bus),
            "network": NetworkInfoAdapter(bus),
            "system": SystemInfoAdapter(bus),
            "tracking": mount,
        }
```

- [ ] **Step 2 : Supprimer le legacy adapter**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git rm backend/astro_brain/adapters/nexstar_adapter.py
```

- [ ] **Step 3 : Mettre à jour `pyproject.toml` — drop nexstarpy, add pyindi-client**

Modifier `backend/pyproject.toml` :

```toml
[project.optional-dependencies]
hardware = [
    "pyindi-client>=2.0",
    "gpsd-py3",
]
```

(`pyserial` n'est plus nécessaire — c'était une dep transitive de nexstarpy.)

- [ ] **Step 4 : Re-sync les deps en mode dev (sans extra hardware)**

```bash
cd backend
uv sync
```

Expected: les deps non-hardware se résolvent sans tenter d'installer `pyindi-client`.

- [ ] **Step 5 : Run la suite complète avec fakes uniquement**

```bash
cd backend
uv run pytest -q
```

Expected: tous les tests passent — `app.py` n'importe `mount_indi_adapter` que dans la branche `use_hardware=True`, jamais déclenchée en test.

- [ ] **Step 6 : Lint**

```bash
cd backend
uv run ruff check .
```

Expected: clean.

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/app.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): wire MountIndiAdapter in app.py, drop nexstarpy dep"
```

(Si `uv sync` n'a pas modifié `uv.lock`, le `git add` du lock sera no-op — c'est OK.)

---

## Task 11 : Service systemd `indiserver` + ordering

Crée un unit qui lance `indiserver -v indi_celestron_aux` sur loopback. Met à jour `astro-brain.service` pour `Requires=` + `After=`. Met à jour `install.sh` pour copier les deux units.

**Files:**
- Create: `backend/deploy/indiserver.service`
- Modify: `backend/deploy/astro-brain.service`
- Modify: `backend/deploy/install.sh`

- [ ] **Step 1 : Écrire l'unit indiserver**

```ini
# backend/deploy/indiserver.service
[Unit]
Description=INDI server (Celestron AUX driver)
Documentation=https://docs.indilib.org/
After=network.target

[Service]
Type=simple
User=pascal3100
# -v: verbose log to journal (essential for debug). -p 7624: explicit port.
# Bind on loopback only — see ADR 2026-05-01 (no remote EKOS in v0.2).
ExecStart=/usr/bin/indiserver -v -p 7624 indi_celestron_aux
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2 : Mettre à jour `astro-brain.service`**

Modifier `backend/deploy/astro-brain.service` — section `[Unit]` :

```ini
[Unit]
Description=Astro-Brain backend (FastAPI)
After=network-online.target gpsd.service indiserver.service
Wants=network-online.target
Requires=indiserver.service
```

(Les autres lignes inchangées.)

- [ ] **Step 3 : Mettre à jour `install.sh`**

Modifier `backend/deploy/install.sh` — entre `uv sync --extra hardware` et `Installing systemd unit...` :

```bash
echo "Installing INDI server systemd unit..."
sudo cp deploy/indiserver.service /etc/systemd/system/indiserver.service
sudo systemctl daemon-reload
sudo systemctl enable indiserver.service
sudo systemctl restart indiserver.service
```

- [ ] **Step 4 : Vérifier la cohérence shellcheck**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
shellcheck backend/deploy/install.sh 2>&1 || true
```

Expected: pas d'erreur bloquante (warnings éventuels acceptables, on n'a pas changé le pattern).

- [ ] **Step 5 : Commit**

```bash
git add backend/deploy/indiserver.service backend/deploy/astro-brain.service backend/deploy/install.sh
git commit -m "deploy: indiserver systemd unit + ordering with astro-brain.service"
```

---

## Task 12 : Patch upstream `indi_celestron_aux` — backlash mount-axis

Patch C++ du driver pour exposer une property `MOUNT_AXIS_BACKLASH` (Number RW × 4) qui mappe les opcodes AUX `MC_SET_POS_BACKLASH=0x10`, `MC_SET_NEG_BACKLASH=0x11`, `MC_GET_POS_BACKLASH=0x40`, `MC_GET_NEG_BACKLASH=0x41`. Travail séparé du repo Astro-Brain : exécuté dans `/tmp/indi-research/indi-3rdparty/` (déjà cloné), branche `astro-brain-backlash`. Le patch est testé sur le Pi à la Task 13 ; ici on produit le code et le `.deb`.

**Files (dans le clone `/tmp/indi-research/indi-3rdparty/indi-celestronaux/`) :**
- Modify: `auxproto.h`
- Modify: `celestronaux.h`
- Modify: `celestronaux.cpp`

- [ ] **Step 1 : Préparer le fork**

```bash
cd /tmp/indi-research/indi-3rdparty
git remote -v  # vérifier que origin = indilib/indi-3rdparty
git checkout -b astro-brain-backlash
```

Expected: branche créée à partir de master upstream.

- [ ] **Step 2 : Ajouter les opcodes AUX dans `auxproto.h`**

Dans `/tmp/indi-research/indi-3rdparty/indi-celestronaux/auxproto.h`, dans l'enum `AUXCommands` (autour de la ligne 33-65), insérer **après** `MC_AUX_GUIDE_ACTIVE = 0x27,` :

```cpp
    MC_SET_POS_BACKLASH  = 0x10,
    MC_SET_NEG_BACKLASH  = 0x11,
    MC_GET_POS_BACKLASH  = 0x40,
    MC_GET_NEG_BACKLASH  = 0x41,
```

⚠️ Les valeurs `0x10` et `0x11` apparaissent aussi dans l'enum `AUXTargets` mais comme `AZM`/`ALT` — c'est le même octet réutilisé dans deux champs distincts (target/source vs opcode), pas un conflit C++.

- [ ] **Step 3 : Déclarer la property + méthodes dans `celestronaux.h`**

Dans `/tmp/indi-research/indi-3rdparty/indi-celestronaux/celestronaux.h`, dans la classe `CelestronAUX`, section `private:` (proche des autres `INumber*`/`ISwitch*` declarations) :

```cpp
    INumber MountAxisBacklashN[4];
    INumberVectorProperty MountAxisBacklashNP;

    bool getBacklash(uint8_t motor, uint8_t direction, uint8_t &outValue);
    bool setBacklash(uint8_t motor, uint8_t direction, uint8_t value);
    void readAllBacklash();
```

`motor` ∈ `{AZM, ALT}` (déjà dans `AUXTargets`), `direction` ∈ `{0=POS, 1=NEG}`.

- [ ] **Step 4 : Initialiser la property dans `initProperties()`**

Dans `celestronaux.cpp`, méthode `initProperties()` (vers ligne 290), après le bloc `CordWrap` :

```cpp
    // Mount-axis backlash (4 values, AZ_POS / AZ_NEG / ALT_POS / ALT_NEG, 0..99)
    IUFillNumber(&MountAxisBacklashN[0], "AZ_POS",  "AZ +",  "%.0f", 0., 99., 1., 0.);
    IUFillNumber(&MountAxisBacklashN[1], "AZ_NEG",  "AZ -",  "%.0f", 0., 99., 1., 0.);
    IUFillNumber(&MountAxisBacklashN[2], "ALT_POS", "ALT +", "%.0f", 0., 99., 1., 0.);
    IUFillNumber(&MountAxisBacklashN[3], "ALT_NEG", "ALT -", "%.0f", 0., 99., 1., 0.);
    IUFillNumberVector(&MountAxisBacklashNP, MountAxisBacklashN, 4,
                       getDeviceName(), "MOUNT_AXIS_BACKLASH",
                       "Backlash", MOTION_TAB, IP_RW, 60, IPS_IDLE);
```

- [ ] **Step 5 : Exposer la property dans `updateProperties()`**

Dans `celestronaux.cpp`, méthode `updateProperties()`, dans la branche `if (isConnected())`, après la définition de `CordWrap` :

```cpp
        defineProperty(&MountAxisBacklashNP);
        readAllBacklash();
```

Et dans la branche `else`, parmi les `deleteProperty(...)` :

```cpp
        deleteProperty(MountAxisBacklashNP.name);
```

- [ ] **Step 6 : Implémenter `getBacklash`/`setBacklash`/`readAllBacklash`**

Append à la fin de `celestronaux.cpp` :

```cpp
bool CelestronAUX::getBacklash(uint8_t motor, uint8_t direction, uint8_t &outValue)
{
    AUXCommands cmd = (direction == 0) ? MC_GET_POS_BACKLASH : MC_GET_NEG_BACKLASH;
    AUXCommand command(cmd, APP, motor);
    if (!sendAUXCommand(command))
        return false;
    AUXCommand response;
    if (!readAUXResponse(response))
        return false;
    if (response.dataSize() < 1)
        return false;
    outValue = response.data()[0];
    return true;
}

bool CelestronAUX::setBacklash(uint8_t motor, uint8_t direction, uint8_t value)
{
    AUXCommands cmd = (direction == 0) ? MC_SET_POS_BACKLASH : MC_SET_NEG_BACKLASH;
    AUXBuffer payload{value};
    AUXCommand command(cmd, APP, motor, payload);
    if (!sendAUXCommand(command))
        return false;
    AUXCommand response;
    return readAUXResponse(response);
}

void CelestronAUX::readAllBacklash()
{
    uint8_t v = 0;
    if (getBacklash(AZM, 0, v)) MountAxisBacklashN[0].value = v;
    if (getBacklash(AZM, 1, v)) MountAxisBacklashN[1].value = v;
    if (getBacklash(ALT, 0, v)) MountAxisBacklashN[2].value = v;
    if (getBacklash(ALT, 1, v)) MountAxisBacklashN[3].value = v;
    MountAxisBacklashNP.s = IPS_OK;
    IDSetNumber(&MountAxisBacklashNP, nullptr);
}
```

⚠️ Si `sendAUXCommand` / `readAUXResponse` ne sont pas les noms réels du driver, ouvrir `celestronaux.cpp` et chercher comment les autres méthodes (par ex. cordwrap) envoient/reçoivent leurs commandes AUX — adapter l'appel en conséquence (souvent `sendAUXCommand(cmd)` avec retour bool, et un buffer accessible via `cmd.response()` ou via callback `processResponse`). Le but reste le même : envoyer un AUXCommand et récupérer 1 octet de réponse.

- [ ] **Step 7 : Override `ISNewNumber` pour intercepter le set client**

Dans `celestronaux.cpp`, méthode `ISNewNumber(...)` (recherche `if (strcmp(name, "GUIDE_RATE") == 0)` ou similaire), ajouter un branch :

```cpp
    if (strcmp(name, "MOUNT_AXIS_BACKLASH") == 0)
    {
        IUUpdateNumber(&MountAxisBacklashNP, values, names, n);
        bool ok = true;
        ok &= setBacklash(AZM, 0, static_cast<uint8_t>(MountAxisBacklashN[0].value));
        ok &= setBacklash(AZM, 1, static_cast<uint8_t>(MountAxisBacklashN[1].value));
        ok &= setBacklash(ALT, 0, static_cast<uint8_t>(MountAxisBacklashN[2].value));
        ok &= setBacklash(ALT, 1, static_cast<uint8_t>(MountAxisBacklashN[3].value));
        MountAxisBacklashNP.s = ok ? IPS_OK : IPS_ALERT;
        IDSetNumber(&MountAxisBacklashNP, nullptr);
        return true;
    }
```

- [ ] **Step 8 : Build local du driver**

```bash
cd /tmp/indi-research/indi-3rdparty
mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ..
make -j4 indi_celestron_aux
```

Expected: compile sans warning bloquant. Binaire dans `build/indi-celestronaux/indi_celestron_aux`.

- [ ] **Step 9 : Smoke test en local sans matériel (le binaire doit au moins démarrer en simulator-less mode)**

```bash
/tmp/indi-research/indi-3rdparty/build/indi-celestronaux/indi_celestron_aux --help 2>&1 | head -5
```

Expected: pas de crash. (Le driver écoute sur stdin/stdout pour XML — un `--help` peut juste echo banner ou ne rien écrire ; l'absence de segfault est le signal positif.)

- [ ] **Step 10 : Build le `.deb` reproductible**

Créer un script `backend/deploy/build-indi-celestronaux.sh` dans le repo Astro-Brain :

```bash
#!/usr/bin/env bash
# Build the patched indi_celestron_aux .deb on the Pi.
# Pre-req: ~/code/indi-3rdparty checked out on branch astro-brain-backlash.
set -euo pipefail

REPO="${HOME}/code/indi-3rdparty"
test -d "${REPO}" || { echo "Expected ${REPO} (clone of indilib/indi-3rdparty)"; exit 1; }
cd "${REPO}"

git fetch origin
git checkout astro-brain-backlash
git pull --ff-only origin astro-brain-backlash || true

mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release -DCPACK_GENERATOR=DEB ..
make -j"$(nproc)" indi_celestron_aux
cpack -G DEB -D CPACK_PACKAGE_NAME=indi-celestronaux

DEB="$(ls -t indi-celestronaux*.deb | head -1)"
echo "Built: ${DEB}"
sudo apt install -y "./${DEB}"
sudo apt-mark hold indi-celestronaux

echo "Installed and held. Restart indiserver: sudo systemctl restart indiserver"
```

```bash
chmod +x /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/deploy/build-indi-celestronaux.sh
```

- [ ] **Step 11 : Commit dans le fork**

```bash
cd /tmp/indi-research/indi-3rdparty
git add indi-celestronaux/auxproto.h indi-celestronaux/celestronaux.h indi-celestronaux/celestronaux.cpp
git commit -m "feat(celestronaux): expose MOUNT_AXIS_BACKLASH (4 values via MC_*_BACKLASH AUX opcodes)"
```

- [ ] **Step 12 : Commit le script de build dans Astro-Brain**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/deploy/build-indi-celestronaux.sh
git commit -m "deploy: script de build local du driver indi_celestron_aux patché"
```

- [ ] **Step 13 : Pousser le fork sur GitHub perso pour PR ultérieure**

```bash
cd /tmp/indi-research/indi-3rdparty
git remote add astro-brain git@github.com:pascal-lopez/indi-3rdparty.git 2>/dev/null || true
git push -u astro-brain astro-brain-backlash
```

(Si l'utilisateur n'a pas encore forké le repo sur son compte GitHub, sauter cette étape et noter dans `journal.md` qu'il faut forker + pousser plus tard.)

---

## Task 13 : Documentation — `architecture.md`, `deployment.md`, `INTEGRATION_CHECKLIST.md`

**Files:**
- Modify: `docs/technical/architecture.md`
- Modify: `docs/technical/deployment.md`
- Modify: `backend/deploy/INTEGRATION_CHECKLIST.md`

- [ ] **Step 1 : Ouvrir et mettre à jour `architecture.md`**

Lire `docs/technical/architecture.md`, puis remplacer toute mention de `nexstarpy`/protocole NexStar direct par la mention de la stack INDI :
- Diagramme : ajouter une boîte `indiserver` entre FastAPI et `/dev/ttyUSB0`.
- Section communication : décrire les trois processus (FastAPI, indiserver, gpsd) et l'ordre systemd.
- Section dépendances : `pyindi-client` au lieu de `nexstarpy`.

(Suivre le style des autres docs : sections courtes, lien vers `indi-reference.md` pour les détails.)

- [ ] **Step 2 : Ajouter la section build local au `deployment.md`**

Lire `docs/technical/deployment.md`. Ajouter une section :

```markdown
## Driver INDI patché (backlash mount-axis)

Le driver upstream `indi_celestron_aux` n'expose pas le backlash mount-axis. Astro-Brain en utilise un fork patché jusqu'au merge de la PR upstream.

Procédure de (re)build sur le Pi :

```bash
~/code/astro-brain/backend/deploy/build-indi-celestronaux.sh
sudo systemctl restart indiserver
```

Le paquet est tenu (`apt-mark hold`) pour qu'`apt upgrade` ne l'écrase pas. Quand la PR upstream est mergée :

```bash
sudo apt-mark unhold indi-celestronaux
sudo apt update && sudo apt upgrade indi-celestronaux
```
```

- [ ] **Step 3 : Mettre à jour `INTEGRATION_CHECKLIST.md`**

Lire `backend/deploy/INTEGRATION_CHECKLIST.md`. Ajouter en tête de la **Section 0** :

```markdown
### Stack INDI

- [ ] `sudo apt install indi-bin python3-indi-client libindi1` (paquet PPA INDI activé)
- [ ] Driver patché installé via `backend/deploy/build-indi-celestronaux.sh` (cf. `docs/technical/deployment.md`)
- [ ] `dpkg -l indi-celestronaux` affiche le paquet `holds` (`apt-mark showhold | grep indi-celestronaux`)
- [ ] `sudo systemctl --no-pager status indiserver.service` → active (running)
- [ ] `sudo journalctl -u indiserver.service -n 30 --no-pager` → driver `indi_celestron_aux` chargé, pas de "ERROR" récurrent
- [ ] Côté workstation, port forward SSH si besoin de debug avec `INDI Control Panel` : `ssh -L 7624:localhost:7624 astro-brain` puis pointer le client local sur `localhost:7624`
```

Et **réécrire la Section 3 (Mount — smoke test)** pour refléter les nouvelles propriétés :

```markdown
## 3. Mount — smoke test (INDI)

Prérequis : monture sous tension, dongle CP2102 sur USB Pi, indiserver actif, driver patché installé.

- [ ] Au démarrage, `mount.state` atteint `ready` avec `details.device="Celestron AUX"`
- [ ] `tracking.state` apparaît à `off` (publish initial dans `MountIndiAdapter.start()`)
- [ ] `POST /slew` `{"axis":"alt","direction":"+","rate":4}` → slew visible ; `mount.state=moving` avec `details.active_slews` peuplé
- [ ] `POST /stop` `{}` → `TELESCOPE_ABORT_MOTION` envoyé ; `mount.state=ready`
- [ ] `POST /tracking` `{"enabled":true}` → drive RA s'engage ; `tracking.state=sidereal`
- [ ] `POST /tracking` `{"enabled":false}` → tracking coupé ; `tracking.state=off`
- [ ] Débrancher le dongle USB → `mount.state=error` dans ≤ 3 s (callback `serverDisconnected` du driver) ; rebrancher + `sudo systemctl restart astro-brain` → `mount.state=ready`

### Backlash (driver patché)

- [ ] Côté Python : `curl -X POST localhost:8000/admin/backlash -d '{"axis":"alt","direction":"+","value":15}'` (à activer si endpoint admin exposé en v0.2 Setup ; sinon test via Python REPL `await mount.set_backlash("alt", "+", 15)`)
- [ ] `await mount.get_backlash("alt", "+")` retourne 15 après set
- [ ] Vérifier dans `INDI Control Panel` (port-forwarded) que `MOUNT_AXIS_BACKLASH.ALT_POS = 15`
- [ ] `i2cdetect`-style : depuis Python, `client.getDevice("Celestron AUX").getNumber("MOUNT_AXIS_BACKLASH")` ne renvoie pas `None`

### Cordwrap

- [ ] `await mount.cordwrap_set_enabled(True)` → property `CORDWRAP.INDI_ENABLED=ON` (visible dans INDI Control Panel)
- [ ] `await mount.cordwrap_get_enabled()` → `True`
- [ ] `await mount.cordwrap_set_position("E")` → `CORDWRAP_POS.CORDWRAP_E=ON`
```

- [ ] **Step 4 : Lint markdown (visuel)**

Ouvrir les 3 fichiers, vérifier rendus tableaux et fences code.

- [ ] **Step 5 : Commit**

```bash
git add docs/technical/architecture.md docs/technical/deployment.md backend/deploy/INTEGRATION_CHECKLIST.md
git commit -m "docs: bascule architecture.md/deployment.md/INTEGRATION_CHECKLIST sur stack INDI"
```

---

## Task 14 : Smoke test E2E sur le Pi

Déploiement réel + déroulé du checklist mis à jour. Cette task est manuelle / sur hardware et ne se valide qu'avec la monture branchée.

**Files:**
- Run only

- [ ] **Step 1 : Sur la workstation, push la branche**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git push -u origin feat/mount-indi
```

- [ ] **Step 2 : Sur le Pi, pull + déployer**

```bash
ssh astro-brain
cd ~/code/astro-brain
git fetch && git checkout feat/mount-indi && git pull
cd backend
bash deploy/install.sh
```

Expected: `astro-brain.service` redémarre `active (running)`, `indiserver.service` aussi.

- [ ] **Step 3 : Build + install du driver patché**

```bash
# si pas déjà fait, cloner le fork sur le Pi :
# git clone -b astro-brain-backlash https://github.com/pascal-lopez/indi-3rdparty.git ~/code/indi-3rdparty
~/code/astro-brain/backend/deploy/build-indi-celestronaux.sh
sudo systemctl restart indiserver
```

Expected: build sans erreur, `dpkg -l indi-celestronaux` affiche la version locale.

- [ ] **Step 4 : Dérouler `INTEGRATION_CHECKLIST.md` sections 0 (stack INDI), 3 (Mount), backlash, cordwrap**

Cocher au fil de l'eau dans le fichier. Noter en bas du checklist (`### Findings`) tout écart entre comportement attendu et réel — en particulier :
- Nom du device INDI (peut être `Celestron AUX` ou autre selon driver — ajuster `INDI_DEVICE_NAME` dans l'adapter si nécessaire).
- Baud rate (HC pass-through 9600, `PORT_TYPE` à confirmer en runtime).
- Comportement de `serverDisconnected` au unplug USB.

- [ ] **Step 5 : Mettre à jour le journal de session**

Ouvrir `docs/project/journal.md`, ajouter une entrée datée 2026-05-01 résumant la migration (livraison) et les `Findings` notables. Respecter le plafond 5-6 sessions (archiver l'ancienne en `journal/archive/<milestone>.md` si nécessaire — voir convention CLAUDE.md).

- [ ] **Step 6 : Commit final + merge**

```bash
git add docs/project/journal.md backend/deploy/INTEGRATION_CHECKLIST.md
git commit -m "docs(journal): session 2026-05-01 — migration mount nexstarpy → INDI"
# Sur la workstation :
git checkout main
git merge --no-ff feat/mount-indi
git push origin main
```

(Pas de PR GitHub — repo perso, merge local.)

---

## Récapitulatif des commits attendus

1. `feat(backend): pure INDI property helpers (set_number, set_switch, state)`
2. `test(backend): programmable FakeIndiClient for adapter tests`
3. `feat(backend): MountIndiAdapter skeleton (start/stop, device discovery)`
4. `feat(backend): MountIndiAdapter slew/stop_slew via TELESCOPE_MOTION_*`
5. `feat(backend): MountIndiAdapter set_time/set_location via TIME_UTC/GEOGRAPHIC_COORD`
6. `feat(backend): MountIndiAdapter set_tracking via TELESCOPE_TRACK_STATE`
7. `feat(backend): MountIndiAdapter cordwrap (enabled + position 4 cardinaux)`
8. `feat(backend): MountIndiAdapter backlash 4-values (depends on driver patch)`
9. `feat(backend): AstroBrainIndiClient (PyIndi.BaseClient bridging to StateBus)`
10. `feat(backend): wire MountIndiAdapter in app.py, drop nexstarpy dep`
11. `deploy: indiserver systemd unit + ordering with astro-brain.service`
12. `deploy: script de build local du driver indi_celestron_aux patché`
13. `docs: bascule architecture.md/deployment.md/INTEGRATION_CHECKLIST sur stack INDI`
14. `docs(journal): session 2026-05-01 — migration mount nexstarpy → INDI`

Plus, dans le repo `indi-3rdparty` (fork) : `feat(celestronaux): expose MOUNT_AXIS_BACKLASH (4 values via MC_*_BACKLASH AUX opcodes)`.

## Risques d'exécution à surveiller

- **`pyindi-client` indispo en wheel pip** : sur le Pi, `apt install python3-indi-client` est probablement requis (bindings SWIG sur libindi). Si `uv sync --extra hardware` échoue à compiler `pyindi-client`, fallback : installer le paquet apt et passer à un import lazy de `PyIndi` qui pioche dans le site-packages système (`PYTHONPATH` ou `--system-site-packages` sur le venv `uv`). À résoudre au déploiement Task 14, **ne pas pré-empter dans le code** ici.
- **Nom du device INDI** : `INDI_DEVICE_NAME = "Celestron AUX"` est une supposition. À confirmer sur le Pi via `indi_getprop -h localhost '*.CONNECTION'` une fois le driver lancé. Ajuster l'adapter si le nom diffère.
- **Baud rate / PORT_TYPE** : pour le HC pass-through, le driver attend `PORT_TYPE=PORT_HC_USB` et baud 9600 (cf. `celestronaux.cpp:140`). L'adapter actuel ne pousse PAS `PORT_TYPE` — il s'appuie sur le default. Si la connexion échoue, ajouter un push `PORT_TYPE` dans `MountIndiAdapter.start()` après `_await_device`.
- **Property `MOUNT_AXIS_BACKLASH` absente avant install du driver patché** : géré explicitement dans Task 8 (lecture renvoie 0, écriture publie `mount=error`). Pas de surprise.
