# Astro-Brain v0.1 Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that runs on the Raspberry Pi, exposing REST commands (`/slew`, `/stop`, `/tracking`, `/state`) and an SSE event stream (`/events`) consumed by the Flutter app.

**Architecture:** Hexagonal (ports + adapters). All business logic — state models, aggregator, StateBus, REST routes, SSE — is hardware-independent and fully testable on the workstation with fake adapters. Real hardware adapters (nexstarpy, gpsd, sysfs) plug in via a runtime selector and are exercised on the Pi. State flows through a central in-memory `StateBus` that broadcasts updates to every connected SSE client.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, sse-starlette, pytest + pytest-asyncio + httpx, nexstarpy (Pi only), gpsd-py3 (Pi only). Dependencies managed with `uv`; `uv.lock` committed for reproducibility.

**Dev workflow reminder:** The code lives in a monorepo at `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/` on the workstation and is cloned to `~/code/astro-brain/` on the Pi. All tasks except 12–17 run comfortably on the workstation against fake adapters; tasks 12–16 wire the real hardware adapters and are validated on the Pi; task 17 is a manual hardware checklist.

---

## File Structure

Paths are relative to the repo root `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/`.

### Repo-level

| File | Responsibility | Created in |
|------|----------------|-----------|
| `.gitignore` | Ignore venvs, caches, build artifacts, `.superpowers/` | ✅ done |
| `README.md` | High-level project intro | Task 1 |

### Backend package

| File | Responsibility | Created in |
|------|----------------|-----------|
| `backend/pyproject.toml` | Package metadata + deps + pytest/ruff config | ✅ done |
| `backend/uv.lock` | Pinned dependency lockfile (committed) | ✅ done |
| `backend/.python-version` | Pins workstation Python to 3.13 | ✅ done |
| `backend/README.md` | Dev setup for backend (uv, tests, run) | Task 1 |
| `backend/astro_brain/__init__.py` | Package marker | ✅ done |
| `backend/astro_brain/subsystems.py` | Enums + `SubsystemState` dataclass | ✅ done |
| `backend/astro_brain/system_state.py` | `SystemState` composite + serialization | ✅ done |
| `backend/astro_brain/aggregator.py` | Pure function computing `overall` | ✅ done |
| `backend/astro_brain/bus.py` | `StateBus` (pub/sub in-memory, asyncio) | ✅ done |
| `backend/astro_brain/services/interfaces.py` | `Protocol` types for each service | ✅ done |
| `backend/astro_brain/services/fakes.py` | Programmable fake services for tests + local dev | ✅ done |
| `backend/astro_brain/api_models.py` | Pydantic request/response models | ✅ done |
| `backend/astro_brain/routes/commands.py` | POST /slew /stop /tracking | ✅ done |
| `backend/astro_brain/routes/state.py` | GET /state | ✅ done |
| `backend/astro_brain/routes/events.py` | GET /events (SSE) | ✅ done |
| `backend/astro_brain/orchestrator.py` | Listens to bus, triggers set_time/set_location | ✅ done |
| `backend/astro_brain/app.py` | FastAPI app factory, wires services | ✅ done |
| `backend/astro_brain/main.py` | Entry point (`uvicorn` launcher with CLI flag) | ✅ done |
| `backend/astro_brain/adapters/system_info.py` | Reads `/sys/class/thermal`, `/proc/loadavg` | ✅ done |
| `backend/astro_brain/adapters/network_info.py` | Reads `/sys/class/net`, runs `iwgetid` | Task 13 |
| `backend/astro_brain/adapters/gpsd_adapter.py` | Consumes gpsd stream | Task 14 |
| `backend/astro_brain/adapters/nexstar_adapter.py` | Wraps nexstarpy | Task 15 |
| `backend/deploy/astro-brain.service` | systemd unit | Task 16 |
| `backend/deploy/install.sh` | Install script run on the Pi | Task 16 |
| `backend/deploy/INTEGRATION_CHECKLIST.md` | Manual hardware test checklist | Task 17 |

### Tests

| File | Responsibility | Created in |
|------|----------------|-----------|
| `backend/tests/__init__.py` | Package marker | ✅ done |
| `backend/tests/test_subsystems.py` | Tests for state dataclasses and enums | ✅ done |
| `backend/tests/test_aggregator.py` | Tests for `overall` computation | ✅ done |
| `backend/tests/test_bus.py` | Tests for StateBus pub/sub | ✅ done |
| `backend/tests/test_fakes.py` | Tests for fake services | ✅ done |
| `backend/tests/test_commands.py` | Integration tests for REST commands | ✅ done |
| `backend/tests/test_state_endpoint.py` | Integration tests for GET /state | ✅ done |
| `backend/tests/test_events_endpoint.py` | Integration tests for SSE /events | ✅ done |
| `backend/tests/test_orchestrator.py` | Tests for the orchestrator logic | ✅ done |

---

## Task 1: Finish scaffold — READMEs, smoke test, clone on Pi

**Status:** Repo init, GitHub push, `uv` + Python 3.13, venv, `pyproject.toml`, `uv.lock`, `.gitignore`, `.python-version`, and package markers (`backend/astro_brain/__init__.py`, `backend/tests/__init__.py`) are already in place — set up during initial project bootstrap. What remains before starting Task 2.

**Files to create:**
- Create: `README.md` (repo root)
- Create: `backend/README.md`
- Create: `backend/tests/test_package.py`

- [ ] **Step 1.1: Write repo-root `README.md`**

Create `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/README.md`:

```markdown
# Astro-Brain

Autonomous control system for a DIY astronomy setup — FastAPI backend on Raspberry Pi + Flutter app.

## Structure

- `backend/` — Python/FastAPI backend that runs on the Raspberry Pi. Controls a Celestron mount via USB-serial (NexStar protocol), reads GPS from a DroTek module, and exposes REST commands + SSE state stream.
- `app/` — Flutter application installed on a phone. Provides the joystick UI, system diagnostics, and (v0.3+) an observation planner.
- `docs/` — Specs, plans, journal, hardware architecture.

See `docs/superpowers/specs/` for design specs and `docs/superpowers/plans/` for implementation plans.
```

- [ ] **Step 1.2: Write `backend/README.md`**

Create `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/README.md`:

````markdown
# Astro-Brain Backend

FastAPI backend that runs on the Raspberry Pi and controls the Celestron mount.

Dependencies are managed with [`uv`](https://docs.astral.sh/uv/). The lockfile (`uv.lock`) is committed.

## Dev setup (workstation)

```bash
cd backend
uv sync
uv run pytest
```

All tests run against fake services — no hardware required.

## Run locally with fakes

```bash
cd backend
uv run uvicorn astro_brain.main:app --reload --host 0.0.0.0 --port 8000
```

Set `ASTRO_BRAIN_HARDWARE=0` (default) to use fakes.

## Run on the Pi with real hardware

```bash
ssh astro-brain
cd ~/code/astro-brain/backend
uv sync --extra hardware
ASTRO_BRAIN_HARDWARE=1 uv run uvicorn astro_brain.main:app --host 0.0.0.0 --port 8000
```

## Deployment (Pi, systemd)

See `deploy/install.sh` and `deploy/astro-brain.service`.
````

- [ ] **Step 1.3: Write a placeholder smoke test**

Create `backend/tests/test_package.py`:

```python
import astro_brain


def test_package_importable():
    assert astro_brain is not None
```

- [ ] **Step 1.4: Run the smoke test**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
uv run pytest tests/test_package.py -v
```

Expected: `1 passed`.

- [ ] **Step 1.5: Clone the repo on the Pi**

```bash
ssh astro-brain 'mkdir -p ~/code && cd ~/code && git clone https://github.com/Pascal3100/astro-brain.git'
```

Verify:

```bash
ssh astro-brain 'ls ~/code/astro-brain'
```

Expected: lists `CLAUDE.md`, `README.md`, `backend/`, `docs/`.

Note: setting up `uv` + running `uv sync --extra hardware` on the Pi happens in Task 16 (deployment) — the clone alone is enough for now.

- [ ] **Step 1.6: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add README.md backend/README.md backend/tests/test_package.py
git commit -m "chore(backend): add READMEs and package smoke test"
git push
```

---

## Task 2: Subsystem state models

**Files:**
- Create: `backend/astro_brain/subsystems.py`
- Create: `backend/astro_brain/system_state.py`
- Create: `backend/tests/test_subsystems.py`

- [ ] **Step 2.1: Write the failing test for subsystem enums**

Create `backend/tests/test_subsystems.py`:

```python
from datetime import datetime, timezone

import pytest

from astro_brain.subsystems import (
    GpsState,
    MountState,
    NetworkState,
    SubsystemState,
    SystemInfoState,
    TrackingState,
)


def test_mount_states_exist():
    assert MountState.DISCONNECTED.value == "disconnected"
    assert MountState.CONNECTING.value == "connecting"
    assert MountState.READY.value == "ready"
    assert MountState.MOVING.value == "moving"
    assert MountState.ERROR.value == "error"


def test_gps_states_exist():
    assert {s.value for s in GpsState} == {
        "off",
        "no_fix",
        "searching",
        "fix_2d",
        "fix_3d",
    }


def test_tracking_states_exist():
    assert {s.value for s in TrackingState} == {"off", "sidereal"}


def test_network_states_exist():
    assert {s.value for s in NetworkState} == {"offline", "client", "hotspot"}


def test_system_info_states_exist():
    assert {s.value for s in SystemInfoState} == {"ok", "warning", "critical"}


def test_subsystem_state_roundtrip():
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=timezone.utc)
    s = SubsystemState(
        state="ready",
        details={"firmware_version": "11.01"},
        since=now,
        message=None,
    )
    assert s.state == "ready"
    assert s.details == {"firmware_version": "11.01"}
    assert s.since == now
    assert s.message is None


def test_subsystem_state_serializable_to_dict():
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=timezone.utc)
    s = SubsystemState(state="fix_3d", details={"satellites": 8}, since=now)
    d = s.to_dict()
    assert d["state"] == "fix_3d"
    assert d["details"] == {"satellites": 8}
    assert d["since"] == "2026-04-17T20:30:00+00:00"
    assert d["message"] is None
```

- [ ] **Step 2.2: Run it and verify it fails**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
pytest tests/test_subsystems.py -v
```

Expected: fails with `ModuleNotFoundError: No module named 'astro_brain.subsystems'`.

- [ ] **Step 2.3: Implement `backend/astro_brain/subsystems.py`**

```python
"""State enums and the generic SubsystemState dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MountState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    MOVING = "moving"
    ERROR = "error"


class GpsState(str, Enum):
    OFF = "off"
    NO_FIX = "no_fix"
    SEARCHING = "searching"
    FIX_2D = "fix_2d"
    FIX_3D = "fix_3d"


class TrackingState(str, Enum):
    OFF = "off"
    SIDEREAL = "sidereal"


class NetworkState(str, Enum):
    OFFLINE = "offline"
    CLIENT = "client"
    HOTSPOT = "hotspot"


class SystemInfoState(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SubsystemState:
    """Generic state for any subsystem.

    `state` is the string value of the subsystem-specific enum (e.g. "ready").
    `details` is free-form context (lat/lon, firmware version, CPU temp…).
    `since` is the timestamp of the last state change.
    `message` is an optional human-readable error or info string.
    """

    state: str
    details: dict[str, Any] = field(default_factory=dict)
    since: datetime | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "details": dict(self.details),
            "since": self.since.isoformat() if self.since is not None else None,
            "message": self.message,
        }
```

- [ ] **Step 2.4: Run the subsystems tests and verify they pass**

```bash
pytest tests/test_subsystems.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 2.5: Write the failing test for `SystemState`**

Append to `backend/tests/test_subsystems.py` (import):

```python
from astro_brain.system_state import SystemState
```

Then add:

```python
def test_system_state_holds_five_subsystems_and_overall():
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=timezone.utc)
    state = SystemState(
        overall="green",
        subsystems={
            "mount": SubsystemState(state="ready", since=now),
            "gps": SubsystemState(state="fix_3d", since=now),
            "tracking": SubsystemState(state="off", since=now),
            "network": SubsystemState(state="client", since=now),
            "system": SubsystemState(state="ok", since=now),
        },
        seq=1,
        ts=now,
    )
    assert state.overall == "green"
    assert set(state.subsystems) == {"mount", "gps", "tracking", "network", "system"}


def test_system_state_to_dict_includes_all_fields():
    now = datetime(2026, 4, 17, 20, 30, 0, tzinfo=timezone.utc)
    state = SystemState(
        overall="green",
        subsystems={"mount": SubsystemState(state="ready", since=now)},
        seq=42,
        ts=now,
    )
    d = state.to_dict()
    assert d["overall"] == "green"
    assert d["seq"] == 42
    assert d["ts"] == "2026-04-17T20:30:00+00:00"
    assert d["subsystems"]["mount"]["state"] == "ready"
```

- [ ] **Step 2.6: Run — verify it fails**

```bash
pytest tests/test_subsystems.py -v
```

Expected: failure on the new tests with `ModuleNotFoundError: No module named 'astro_brain.system_state'`.

- [ ] **Step 2.7: Implement `backend/astro_brain/system_state.py`**

```python
"""Composite system state: overall + per-subsystem state + monotonic seq."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from astro_brain.subsystems import SubsystemState


@dataclass(frozen=True)
class SystemState:
    overall: str  # "green" | "blue" | "orange" | "red"
    subsystems: dict[str, SubsystemState]
    seq: int
    ts: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "subsystems": {
                name: s.to_dict() for name, s in self.subsystems.items()
            },
            "seq": self.seq,
            "ts": self.ts.isoformat(),
        }
```

- [ ] **Step 2.8: Run and verify pass**

```bash
pytest tests/test_subsystems.py -v
```

Expected: all tests pass.

- [ ] **Step 2.9: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/subsystems.py backend/astro_brain/system_state.py backend/tests/test_subsystems.py
git commit -m "feat(backend): add subsystem state enums and SystemState model"
git push
```

---

## Task 3: Aggregator (compute `overall`)

**Files:**
- Create: `backend/astro_brain/aggregator.py`
- Create: `backend/tests/test_aggregator.py`

The aggregator applies the rules from the spec:

1. Any critical subsystem in `disconnected` / `error` → `red`
2. Any subsystem in `connecting` / `searching` → `blue`
3. Any non-critical subsystem in `no_fix` / `warning` / `critical` / `offline` → `orange`
4. Otherwise → `green`

Critical subsystems in v0.1: **only `mount`**.

- [ ] **Step 3.1: Write the failing test**

Create `backend/tests/test_aggregator.py`:

```python
from astro_brain.aggregator import compute_overall
from astro_brain.subsystems import SubsystemState


def _ss(state: str) -> SubsystemState:
    return SubsystemState(state=state)


def test_all_ready_is_green():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "gps": _ss("fix_3d"),
            "tracking": _ss("sidereal"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "green"


def test_mount_disconnected_is_red():
    result = compute_overall(
        {
            "mount": _ss("disconnected"),
            "gps": _ss("fix_3d"),
            "tracking": _ss("off"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "red"


def test_mount_error_is_red():
    result = compute_overall({"mount": _ss("error")})
    assert result == "red"


def test_mount_connecting_is_blue():
    result = compute_overall(
        {
            "mount": _ss("connecting"),
            "gps": _ss("no_fix"),
        }
    )
    assert result == "blue"


def test_gps_searching_is_blue_even_if_mount_ready():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "gps": _ss("searching"),
        }
    )
    assert result == "blue"


def test_gps_no_fix_with_mount_ready_is_orange():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "gps": _ss("no_fix"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "orange"


def test_system_warning_is_orange():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "system": _ss("warning"),
        }
    )
    assert result == "orange"


def test_network_offline_is_orange():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "network": _ss("offline"),
        }
    )
    assert result == "orange"


def test_mount_moving_is_green():
    result = compute_overall(
        {
            "mount": _ss("moving"),
            "gps": _ss("fix_3d"),
            "tracking": _ss("sidereal"),
            "network": _ss("client"),
            "system": _ss("ok"),
        }
    )
    assert result == "green"


def test_red_beats_blue_when_both_apply():
    result = compute_overall(
        {
            "mount": _ss("error"),
            "gps": _ss("searching"),
        }
    )
    assert result == "red"


def test_blue_beats_orange_when_both_apply():
    result = compute_overall(
        {
            "mount": _ss("ready"),
            "gps": _ss("searching"),
            "system": _ss("warning"),
        }
    )
    assert result == "blue"
```

- [ ] **Step 3.2: Run — verify it fails**

```bash
pytest tests/test_aggregator.py -v
```

Expected: `ModuleNotFoundError: No module named 'astro_brain.aggregator'`.

- [ ] **Step 3.3: Implement `backend/astro_brain/aggregator.py`**

```python
"""Computes the overall system health color from per-subsystem states.

Rules (first match wins):
  1. Any critical subsystem in a fatal state -> "red"
  2. Any subsystem in a transient state     -> "blue"
  3. Any subsystem in a degraded state      -> "orange"
  4. Otherwise                              -> "green"
"""

from __future__ import annotations

from astro_brain.subsystems import SubsystemState

CRITICAL_SUBSYSTEMS: frozenset[str] = frozenset({"mount"})

FATAL_STATES: frozenset[str] = frozenset({"disconnected", "error"})
TRANSIENT_STATES: frozenset[str] = frozenset({"connecting", "searching"})
DEGRADED_STATES: frozenset[str] = frozenset(
    {"no_fix", "warning", "critical", "offline"}
)


def compute_overall(subsystems: dict[str, SubsystemState]) -> str:
    for name, s in subsystems.items():
        if name in CRITICAL_SUBSYSTEMS and s.state in FATAL_STATES:
            return "red"
    for s in subsystems.values():
        if s.state in TRANSIENT_STATES:
            return "blue"
    for s in subsystems.values():
        if s.state in DEGRADED_STATES:
            return "orange"
    return "green"
```

- [ ] **Step 3.4: Run and verify pass**

```bash
pytest tests/test_aggregator.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 3.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/aggregator.py backend/tests/test_aggregator.py
git commit -m "feat(backend): add aggregator computing overall system color"
git push
```

---

## Task 4: StateBus (pub/sub, in-memory)

The `StateBus` is the central hub:

- `publish(subsystem, state)` — update the in-memory state, recompute `overall`, increment `seq`, broadcast an `update` event to subscribers
- `get_full_state()` — return the current `SystemState` snapshot
- `subscribe()` — async iterator that first yields a `snapshot` event then streams `update` events

**Files:**
- Create: `backend/astro_brain/bus.py`
- Create: `backend/tests/test_bus.py`

- [ ] **Step 4.1: Write the failing test**

Create `backend/tests/test_bus.py`:

```python
import asyncio
from datetime import datetime, timezone

import pytest

from astro_brain.bus import Event, StateBus
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_fresh_bus_has_empty_subsystems_green_and_seq_zero():
    bus = StateBus()
    full = bus.get_full_state()
    assert full.overall == "green"
    assert full.subsystems == {}
    assert full.seq == 0


def test_publish_updates_subsystem_and_increments_seq():
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    full = bus.get_full_state()
    assert full.subsystems["mount"].state == "ready"
    assert full.seq == 1
    assert full.overall == "green"


def test_publish_recomputes_overall():
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="error", since=_now()))
    assert bus.get_full_state().overall == "red"


async def test_subscribe_yields_initial_snapshot():
    bus = StateBus()
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    agen = bus.subscribe()
    first = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert first.type == "snapshot"
    assert first.payload["subsystems"]["mount"]["state"] == "ready"
    await agen.aclose()


async def test_subscribe_yields_updates_after_publish():
    bus = StateBus()
    agen = bus.subscribe()
    snapshot = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert snapshot.type == "snapshot"

    bus.publish("gps", SubsystemState(state="fix_3d", since=_now()))
    event = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
    assert event.type == "update"
    assert event.payload["subsystem"] == "gps"
    assert event.payload["state"]["state"] == "fix_3d"
    assert event.payload["seq"] == 1
    await agen.aclose()


async def test_multiple_subscribers_each_get_updates():
    bus = StateBus()
    a = bus.subscribe()
    b = bus.subscribe()
    await asyncio.wait_for(a.__anext__(), timeout=1.0)  # snapshot
    await asyncio.wait_for(b.__anext__(), timeout=1.0)  # snapshot

    bus.publish("system", SubsystemState(state="ok", since=_now()))
    ea = await asyncio.wait_for(a.__anext__(), timeout=1.0)
    eb = await asyncio.wait_for(b.__anext__(), timeout=1.0)
    assert ea.type == "update"
    assert eb.type == "update"
    assert ea.payload["seq"] == 1
    assert eb.payload["seq"] == 1
    await a.aclose()
    await b.aclose()


async def test_unsubscribe_is_clean():
    bus = StateBus()
    agen = bus.subscribe()
    await asyncio.wait_for(agen.__anext__(), timeout=1.0)  # snapshot
    await agen.aclose()
    # publishing after unsubscribe must not raise
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    assert bus.get_full_state().seq == 1
```

- [ ] **Step 4.2: Run and verify failure**

```bash
pytest tests/test_bus.py -v
```

Expected: `ModuleNotFoundError: No module named 'astro_brain.bus'`.

- [ ] **Step 4.3: Implement `backend/astro_brain/bus.py`**

```python
"""In-memory event bus for the backend's system state.

Semantics:
  * publish() is synchronous and non-blocking. It mutates the in-memory
    state, recomputes overall, and pushes an Event to every subscriber's
    queue (bounded; oldest messages are dropped when the queue is full).
  * subscribe() returns an async generator. It first yields a "snapshot"
    Event with the current full state, then yields "update" Events for
    every subsequent publish.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from astro_brain.aggregator import compute_overall
from astro_brain.subsystems import SubsystemState
from astro_brain.system_state import SystemState


SUBSCRIBER_QUEUE_MAX = 64


@dataclass
class Event:
    type: str  # "snapshot" | "update"
    payload: dict[str, Any]


class StateBus:
    def __init__(self) -> None:
        self._subsystems: dict[str, SubsystemState] = {}
        self._seq: int = 0
        self._subscribers: list[asyncio.Queue[Event]] = []

    # --- synchronous public API ---

    def publish(self, subsystem: str, state: SubsystemState) -> None:
        self._subsystems[subsystem] = state
        self._seq += 1
        full = self.get_full_state()
        event = Event(
            type="update",
            payload={
                "subsystem": subsystem,
                "state": state.to_dict(),
                "overall": full.overall,
                "seq": self._seq,
                "ts": full.ts.isoformat(),
            },
        )
        self._broadcast(event)

    def get_full_state(self) -> SystemState:
        return SystemState(
            overall=compute_overall(self._subsystems),
            subsystems=dict(self._subsystems),
            seq=self._seq,
            ts=datetime.now(timezone.utc),
        )

    # --- async subscription ---

    async def subscribe(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
        self._subscribers.append(queue)
        try:
            full = self.get_full_state()
            yield Event(type="snapshot", payload=full.to_dict())
            while True:
                event = await queue.get()
                yield event
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    # --- internal ---

    def _broadcast(self, event: Event) -> None:
        for q in self._subscribers:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)
```

- [ ] **Step 4.4: Run and verify pass**

```bash
pytest tests/test_bus.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 4.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/bus.py backend/tests/test_bus.py
git commit -m "feat(backend): add in-memory StateBus with pub/sub and snapshot"
git push
```

---

## Task 5: Service interfaces + fake implementations

Every service (mount, gps, tracking, network, system) implements a `Protocol`. Fake implementations are programmable so tests and local dev can drive them without hardware.

**Files:**
- Create: `backend/astro_brain/services/__init__.py`
- Create: `backend/astro_brain/services/interfaces.py`
- Create: `backend/astro_brain/services/fakes.py`
- Create: `backend/tests/test_fakes.py`

- [ ] **Step 5.1: Create the services sub-package**

```bash
mkdir -p backend/astro_brain/services
touch backend/astro_brain/services/__init__.py
```

- [ ] **Step 5.2: Write the service interfaces**

Create `backend/astro_brain/services/interfaces.py`:

```python
"""Protocol types for every service.

The REST routes depend on these protocols, not concrete classes. The
backend wires either the Fake* (dev/tests) or the real hardware adapter
(on the Pi) at startup.
"""

from __future__ import annotations

from typing import Literal, Protocol


Axis = Literal["alt", "az"]
Direction = Literal["+", "-"]


class MountService(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None: ...
    async def stop_slew(self, axis: Axis | None) -> None: ...

    async def set_time(self, utc_iso: str) -> None: ...
    async def set_location(self, lat: float, lon: float) -> None: ...


class TrackingService(Protocol):
    async def set_tracking(self, enabled: bool) -> None: ...


class GpsService(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class NetworkService(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...


class SystemInfoService(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

- [ ] **Step 5.3: Write the failing test for the fakes**

Create `backend/tests/test_fakes.py`:

```python
import asyncio

import pytest

from astro_brain.bus import StateBus
from astro_brain.services.fakes import (
    FakeGps,
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
)


async def test_fake_mount_publishes_ready_on_start():
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "ready"
    assert s.details["firmware_version"] == "fake-1.0"


async def test_fake_mount_slew_transitions_to_moving():
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    await mount.slew("alt", "+", 5)
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "moving"
    assert s.details["active_slews"] == [
        {"axis": "alt", "direction": "+", "rate": 5}
    ]


async def test_fake_mount_stop_slew_returns_to_ready():
    bus = StateBus()
    mount = FakeMount(bus)
    await mount.start()
    await mount.slew("alt", "+", 5)
    await mount.stop_slew(None)
    s = bus.get_full_state().subsystems["mount"]
    assert s.state == "ready"
    assert s.details.get("active_slews", []) == []


async def test_fake_tracking_publishes_state():
    bus = StateBus()
    tracking = FakeTracking(bus)
    await tracking.set_tracking(True)
    assert bus.get_full_state().subsystems["tracking"].state == "sidereal"
    await tracking.set_tracking(False)
    assert bus.get_full_state().subsystems["tracking"].state == "off"


async def test_fake_gps_produces_fix_on_start():
    bus = StateBus()
    gps = FakeGps(bus, initial_state="fix_3d", lat=48.85, lon=2.35, sats=8)
    await gps.start()
    s = bus.get_full_state().subsystems["gps"]
    assert s.state == "fix_3d"
    assert s.details["lat"] == 48.85
    assert s.details["lon"] == 2.35
    assert s.details["satellites"] == 8
    await gps.stop()


async def test_fake_network_publishes_client_by_default():
    bus = StateBus()
    net = FakeNetwork(bus, state="client", ssid="Home", ip="192.168.1.10")
    await net.start()
    s = bus.get_full_state().subsystems["network"]
    assert s.state == "client"
    assert s.details["ssid"] == "Home"
    assert s.details["ip"] == "192.168.1.10"
    await net.stop()


async def test_fake_system_info_publishes_ok_within_thresholds():
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=55.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    s = bus.get_full_state().subsystems["system"]
    assert s.state == "ok"
    assert s.details["cpu_temp_c"] == 55.0
    await sys.stop()


async def test_fake_system_info_transitions_to_warning_over_threshold():
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=72.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    assert bus.get_full_state().subsystems["system"].state == "warning"
    await sys.stop()


async def test_fake_system_info_transitions_to_critical_over_threshold():
    bus = StateBus()
    sys = FakeSystemInfo(bus, cpu_temp_c=82.0, cpu_load=0.4, uptime_s=120)
    await sys.start()
    assert bus.get_full_state().subsystems["system"].state == "critical"
    await sys.stop()
```

- [ ] **Step 5.4: Run and verify failure**

```bash
pytest tests/test_fakes.py -v
```

Expected: import error on `astro_brain.services.fakes`.

- [ ] **Step 5.5: Implement the fakes**

Create `backend/astro_brain/services/fakes.py`:

```python
"""Fake service implementations used by tests and local dev.

They are deterministic, synchronous-fast, and programmable — they never
touch hardware. Use them from tests (`test_*`) and when running the
backend with ASTRO_BRAIN_HARDWARE=0 (default).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeMount:
    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._active_slews: list[dict[str, Any]] = []

    async def start(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"firmware_version": "fake-1.0"},
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(state="disconnected", since=_now()),
        )

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        # replace any existing slew on the same axis
        self._active_slews = [s for s in self._active_slews if s["axis"] != axis]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={"active_slews": list(self._active_slews)},
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        if axis is None:
            self._active_slews = []
        else:
            self._active_slews = [
                s for s in self._active_slews if s["axis"] != axis
            ]
        if self._active_slews:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="moving",
                    details={"active_slews": list(self._active_slews)},
                    since=_now(),
                ),
            )
        else:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": "fake-1.0"},
                    since=_now(),
                ),
            )

    async def set_time(self, utc_iso: str) -> None:
        # the fake does not persist time; we just accept the call
        return None

    async def set_location(self, lat: float, lon: float) -> None:
        return None


class FakeTracking:
    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._bus.publish("tracking", SubsystemState(state="off", since=_now()))

    async def set_tracking(self, enabled: bool) -> None:
        value = "sidereal" if enabled else "off"
        self._bus.publish("tracking", SubsystemState(state=value, since=_now()))


class FakeGps:
    def __init__(
        self,
        bus: StateBus,
        *,
        initial_state: str = "fix_3d",
        lat: float = 48.8566,
        lon: float = 2.3522,
        altitude_m: float = 45.0,
        sats: int = 8,
        hdop: float = 0.9,
    ) -> None:
        self._bus = bus
        self._initial_state = initial_state
        self._details = {
            "lat": lat,
            "lon": lon,
            "altitude_m": altitude_m,
            "satellites": sats,
            "hdop": hdop,
        }

    async def start(self) -> None:
        self._bus.publish(
            "gps",
            SubsystemState(
                state=self._initial_state,
                details=dict(self._details),
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish("gps", SubsystemState(state="off", since=_now()))


class FakeNetwork:
    def __init__(
        self,
        bus: StateBus,
        *,
        state: str = "client",
        ssid: str = "fake-wifi",
        ip: str = "192.168.1.10",
    ) -> None:
        self._bus = bus
        self._state = state
        self._ssid = ssid
        self._ip = ip

    async def start(self) -> None:
        self._bus.publish(
            "network",
            SubsystemState(
                state=self._state,
                details={"ssid": self._ssid, "ip": self._ip},
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        self._bus.publish("network", SubsystemState(state="offline", since=_now()))


class FakeSystemInfo:
    WARN_TEMP = 70.0
    CRIT_TEMP = 80.0
    WARN_LOAD = 1.5

    def __init__(
        self,
        bus: StateBus,
        *,
        cpu_temp_c: float = 55.0,
        cpu_load: float = 0.4,
        uptime_s: int = 120,
    ) -> None:
        self._bus = bus
        self._cpu_temp_c = cpu_temp_c
        self._cpu_load = cpu_load
        self._uptime_s = uptime_s

    async def start(self) -> None:
        if self._cpu_temp_c >= self.CRIT_TEMP:
            state = "critical"
        elif self._cpu_temp_c >= self.WARN_TEMP or self._cpu_load >= self.WARN_LOAD:
            state = "warning"
        else:
            state = "ok"
        self._bus.publish(
            "system",
            SubsystemState(
                state=state,
                details={
                    "cpu_temp_c": self._cpu_temp_c,
                    "cpu_load": self._cpu_load,
                    "uptime_s": self._uptime_s,
                },
                since=_now(),
            ),
        )

    async def stop(self) -> None:
        return None
```

- [ ] **Step 5.6: Run tests and verify pass**

```bash
pytest tests/test_fakes.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5.7: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/services/ backend/tests/test_fakes.py
git commit -m "feat(backend): add service interfaces and fake implementations"
git push
```

---

## Task 6: Pydantic API models

**Files:**
- Create: `backend/astro_brain/api_models.py`

These are the wire schemas for REST requests/responses. No dedicated test file — they are exercised through the route tests in Task 7+.

- [ ] **Step 6.1: Create `backend/astro_brain/api_models.py`**

```python
"""Pydantic models for the public REST API wire format."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SlewRequest(BaseModel):
    axis: Literal["alt", "az"]
    direction: Literal["+", "-"]
    rate: int = Field(ge=1, le=9)


class StopRequest(BaseModel):
    axis: Literal["alt", "az"] | None = None


class TrackingRequest(BaseModel):
    enabled: bool


class OkResponse(BaseModel):
    ok: Literal[True] = True
```

- [ ] **Step 6.2: Quick smoke check**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
python -c "from astro_brain.api_models import SlewRequest; print(SlewRequest(axis='alt', direction='+', rate=5))"
```

Expected: prints a `SlewRequest` instance without errors.

- [ ] **Step 6.3: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/api_models.py
git commit -m "feat(backend): add Pydantic API models for REST commands"
git push
```

---

## Task 7: REST command endpoints (/slew, /stop, /tracking)

**Files:**
- Create: `backend/astro_brain/routes/__init__.py`
- Create: `backend/astro_brain/routes/commands.py`
- Create: `backend/astro_brain/deps.py`
- Create: `backend/tests/test_commands.py`

The routes depend on the service protocols via FastAPI `Depends()`, not on concrete classes. Tests override the dependencies with fakes.

- [ ] **Step 7.1: Create the routes sub-package and deps module**

```bash
mkdir -p backend/astro_brain/routes
touch backend/astro_brain/routes/__init__.py
```

Create `backend/astro_brain/deps.py`:

```python
"""FastAPI dependency providers.

The app wires these at startup (see `app.py`) to either fake or real
implementations. Routes depend on the factory callables below.
"""

from __future__ import annotations

from typing import Callable

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import (
    GpsService,
    MountService,
    NetworkService,
    SystemInfoService,
    TrackingService,
)

# These module-level attributes are populated by `app.py` at startup.
# Routes call them to get the currently-wired services.
get_bus: Callable[[], StateBus]
get_mount: Callable[[], MountService]
get_tracking: Callable[[], TrackingService]
get_gps: Callable[[], GpsService]
get_network: Callable[[], NetworkService]
get_system_info: Callable[[], SystemInfoService]


def not_wired() -> object:
    raise RuntimeError(
        "Service dependency not wired. Ensure build_app() was called."
    )


get_bus = not_wired  # type: ignore[assignment]
get_mount = not_wired  # type: ignore[assignment]
get_tracking = not_wired  # type: ignore[assignment]
get_gps = not_wired  # type: ignore[assignment]
get_network = not_wired  # type: ignore[assignment]
get_system_info = not_wired  # type: ignore[assignment]
```

- [ ] **Step 7.2: Write the failing test**

Create `backend/tests/test_commands.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.commands import router
from astro_brain.services.fakes import FakeMount, FakeTracking


@pytest.fixture
def client() -> TestClient:
    bus = StateBus()
    mount = FakeMount(bus)
    tracking = FakeTracking(bus)

    # wire deps
    deps.get_bus = lambda: bus
    deps.get_mount = lambda: mount
    deps.get_tracking = lambda: tracking

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_slew_returns_ok_and_moves_mount(client: TestClient):
    r = client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"


def test_slew_rejects_invalid_axis(client: TestClient):
    r = client.post("/slew", json={"axis": "xx", "direction": "+", "rate": 5})
    assert r.status_code == 422


def test_slew_rejects_rate_out_of_range(client: TestClient):
    r = client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 10})
    assert r.status_code == 422


def test_stop_without_axis_stops_all(client: TestClient):
    client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    client.post("/slew", json={"axis": "az", "direction": "-", "rate": 3})
    r = client.post("/stop", json={})
    assert r.status_code == 200
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "ready"


def test_stop_with_axis_stops_only_that_axis(client: TestClient):
    client.post("/slew", json={"axis": "alt", "direction": "+", "rate": 5})
    client.post("/slew", json={"axis": "az", "direction": "-", "rate": 3})
    r = client.post("/stop", json={"axis": "alt"})
    assert r.status_code == 200
    mount_state = deps.get_bus().get_full_state().subsystems["mount"]
    assert mount_state.state == "moving"
    remaining = [s["axis"] for s in mount_state.details["active_slews"]]
    assert remaining == ["az"]


def test_tracking_toggle(client: TestClient):
    r = client.post("/tracking", json={"enabled": True})
    assert r.status_code == 200
    assert (
        deps.get_bus().get_full_state().subsystems["tracking"].state
        == "sidereal"
    )
    r = client.post("/tracking", json={"enabled": False})
    assert (
        deps.get_bus().get_full_state().subsystems["tracking"].state == "off"
    )
```

- [ ] **Step 7.3: Run and verify failure**

```bash
pytest tests/test_commands.py -v
```

Expected: `ModuleNotFoundError: No module named 'astro_brain.routes.commands'`.

- [ ] **Step 7.4: Implement the commands router**

Create `backend/astro_brain/routes/commands.py`:

```python
"""POST /slew, /stop, /tracking — imperative commands."""

from __future__ import annotations

from fastapi import APIRouter

from astro_brain import deps
from astro_brain.api_models import OkResponse, SlewRequest, StopRequest, TrackingRequest


router = APIRouter(tags=["commands"])


@router.post("/slew", response_model=OkResponse)
async def slew(req: SlewRequest) -> OkResponse:
    mount = deps.get_mount()
    await mount.slew(req.axis, req.direction, req.rate)
    return OkResponse()


@router.post("/stop", response_model=OkResponse)
async def stop(req: StopRequest) -> OkResponse:
    mount = deps.get_mount()
    await mount.stop_slew(req.axis)
    return OkResponse()


@router.post("/tracking", response_model=OkResponse)
async def tracking(req: TrackingRequest) -> OkResponse:
    svc = deps.get_tracking()
    await svc.set_tracking(req.enabled)
    return OkResponse()
```

- [ ] **Step 7.5: Run tests and verify pass**

```bash
pytest tests/test_commands.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 7.6: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/routes/ backend/astro_brain/deps.py backend/tests/test_commands.py
git commit -m "feat(backend): add REST command endpoints (/slew /stop /tracking)"
git push
```

---

## Task 8: GET /state endpoint

**Files:**
- Create: `backend/astro_brain/routes/state.py`
- Create: `backend/tests/test_state_endpoint.py`

- [ ] **Step 8.1: Write the failing test**

Create `backend/tests/test_state_endpoint.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.state import router
from astro_brain.services.fakes import FakeGps, FakeMount


@pytest.fixture
def client() -> TestClient:
    bus = StateBus()
    deps.get_bus = lambda: bus
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_state_empty_bus(client: TestClient):
    r = client.get("/state")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"] == {}
    assert body["seq"] == 0
    assert "ts" in body


async def test_state_after_publishes(client: TestClient):
    bus = deps.get_bus()
    mount = FakeMount(bus)
    gps = FakeGps(bus)
    await mount.start()
    await gps.start()
    r = client.get("/state")
    body = r.json()
    assert body["overall"] == "green"
    assert body["subsystems"]["mount"]["state"] == "ready"
    assert body["subsystems"]["gps"]["state"] == "fix_3d"
    assert body["seq"] == 2
```

- [ ] **Step 8.2: Run and verify failure**

```bash
pytest tests/test_state_endpoint.py -v
```

Expected: import error.

- [ ] **Step 8.3: Implement the state router**

Create `backend/astro_brain/routes/state.py`:

```python
"""GET /state — one-shot full state snapshot."""

from __future__ import annotations

from fastapi import APIRouter

from astro_brain import deps


router = APIRouter(tags=["state"])


@router.get("/state")
async def get_state() -> dict:
    return deps.get_bus().get_full_state().to_dict()
```

- [ ] **Step 8.4: Run tests and verify pass**

```bash
pytest tests/test_state_endpoint.py -v
```

Expected: both tests pass.

- [ ] **Step 8.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/routes/state.py backend/tests/test_state_endpoint.py
git commit -m "feat(backend): add GET /state endpoint"
git push
```

---

## Task 9: SSE /events endpoint

The endpoint wraps `StateBus.subscribe()` into an SSE stream using `sse-starlette`. It yields:

- one `event: snapshot` message on connect
- one `event: update` per `publish()`
- `: ping` comment every 15 s (handled by `sse-starlette`)

**Files:**
- Create: `backend/astro_brain/routes/events.py`
- Create: `backend/tests/test_events_endpoint.py`

- [ ] **Step 9.1: Write the failing test**

Create `backend/tests/test_events_endpoint.py`:

```python
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.routes.events import router
from astro_brain.services.fakes import FakeMount


async def _read_sse_event(lines: list[str]) -> tuple[str, dict]:
    """Parse an SSE block (lines until blank line) into (event, json data)."""
    event = "message"
    data_parts: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_parts.append(line[len("data:") :].strip())
    return event, json.loads("\n".join(data_parts))


async def test_events_stream_emits_snapshot_then_update():
    bus = StateBus()
    mount = FakeMount(bus)
    deps.get_bus = lambda: bus

    app = FastAPI()
    app.include_router(router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        async with client.stream("GET", "/events") as response:
            assert response.status_code == 200

            buffer: list[str] = []
            collected: list[tuple[str, dict]] = []

            async def collect_events(n: int) -> None:
                async for line in response.aiter_lines():
                    if line == "" and buffer:
                        evt = await _read_sse_event(buffer)
                        collected.append(evt)
                        buffer.clear()
                        if len(collected) >= n:
                            return
                    elif line:
                        buffer.append(line)

            # first event: snapshot (sent on connect)
            task = asyncio.create_task(collect_events(1))
            await asyncio.wait_for(task, timeout=2.0)
            assert collected[0][0] == "snapshot"
            assert collected[0][1]["overall"] == "green"

            # trigger an update
            await mount.start()

            # collect one more event
            task = asyncio.create_task(collect_events(2))
            await asyncio.wait_for(task, timeout=2.0)
            assert collected[1][0] == "update"
            assert collected[1][1]["subsystem"] == "mount"
            assert collected[1][1]["state"]["state"] == "ready"
            assert collected[1][1]["seq"] == 1
```

- [ ] **Step 9.2: Run and verify failure**

```bash
pytest tests/test_events_endpoint.py -v
```

Expected: import error.

- [ ] **Step 9.3: Implement the events router**

Create `backend/astro_brain/routes/events.py`:

```python
"""GET /events — SSE stream of system state updates."""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from astro_brain import deps


router = APIRouter(tags=["events"])


PING_INTERVAL_SECONDS = 15


@router.get("/events")
async def events(request: Request) -> EventSourceResponse:
    bus = deps.get_bus()

    async def event_gen() -> AsyncIterator[dict]:
        async for event in bus.subscribe():
            if await request.is_disconnected():
                break
            yield {"event": event.type, "data": json.dumps(event.payload)}

    return EventSourceResponse(event_gen(), ping=PING_INTERVAL_SECONDS)
```

- [ ] **Step 9.4: Run test and verify pass**

```bash
pytest tests/test_events_endpoint.py -v
```

Expected: 1 passed.

- [ ] **Step 9.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/routes/events.py backend/tests/test_events_endpoint.py
git commit -m "feat(backend): add SSE /events endpoint streaming StateBus events"
git push
```

---

## Task 10: Orchestrator (boot sequence: mount + gps → set_time/set_location)

The orchestrator subscribes to the bus. When **both** `mount = ready` and `gps ∈ {fix_2d, fix_3d}` become true, it calls `mount.set_time()` and `mount.set_location()` exactly once, then stays idle until either dependency transitions back out and in again.

**Files:**
- Create: `backend/astro_brain/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`

- [ ] **Step 10.1: Write the failing test**

Create `backend/tests/test_orchestrator.py`:

```python
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.subsystems import SubsystemState


def _now():
    return datetime.now(timezone.utc)


async def _run_briefly(coro):
    task = asyncio.create_task(coro)
    await asyncio.sleep(0.05)
    return task


async def _stop_task(task: asyncio.Task):
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_orchestrator_syncs_when_mount_ready_and_gps_fix():
    bus = StateBus()
    mount = AsyncMock()
    orch = Orchestrator(bus=bus, mount=mount)

    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 48.85, "lon": 2.35},
            since=_now(),
        ),
    )

    task = await _run_briefly(orch.run())

    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 1
    assert mount.set_location.call_count == 1
    ((lat, lon), _) = mount.set_location.call_args
    assert lat == 48.85 and lon == 2.35

    await _stop_task(task)


async def test_orchestrator_does_not_sync_with_no_fix():
    bus = StateBus()
    mount = AsyncMock()
    orch = Orchestrator(bus=bus, mount=mount)

    bus.publish("gps", SubsystemState(state="no_fix", since=_now()))
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.1)

    assert mount.set_time.call_count == 0
    assert mount.set_location.call_count == 0

    await _stop_task(task)


async def test_orchestrator_syncs_only_once_while_conditions_hold():
    bus = StateBus()
    mount = AsyncMock()
    orch = Orchestrator(bus=bus, mount=mount)

    bus.publish(
        "gps",
        SubsystemState(state="fix_3d", details={"lat": 1.0, "lon": 2.0}, since=_now()),
    )
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)

    # extra publishes that do NOT change conditions should not trigger a resync
    bus.publish(
        "gps",
        SubsystemState(
            state="fix_3d",
            details={"lat": 1.0, "lon": 2.0, "satellites": 9},
            since=_now(),
        ),
    )
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    await _stop_task(task)


async def test_orchestrator_resyncs_after_disconnect_reconnect():
    bus = StateBus()
    mount = AsyncMock()
    orch = Orchestrator(bus=bus, mount=mount)

    bus.publish(
        "gps",
        SubsystemState(state="fix_3d", details={"lat": 1.0, "lon": 2.0}, since=_now()),
    )
    task = await _run_briefly(orch.run())
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 1

    # disconnect then reconnect
    bus.publish("mount", SubsystemState(state="disconnected", since=_now()))
    await asyncio.sleep(0.05)
    bus.publish("mount", SubsystemState(state="ready", since=_now()))
    await asyncio.sleep(0.05)
    assert mount.set_time.call_count == 2

    await _stop_task(task)
```

- [ ] **Step 10.2: Run and verify failure**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: import error on `astro_brain.orchestrator`.

- [ ] **Step 10.3: Implement the orchestrator**

Create `backend/astro_brain/orchestrator.py`:

```python
"""Boot orchestrator: syncs the mount with GPS + time when both are ready.

Listens on the StateBus. Triggers mount.set_time() + mount.set_location()
exactly once per (mount ready AND gps fix) transition. If either
condition becomes false, the next time both are true again it will
resync.
"""

from __future__ import annotations

from datetime import datetime, timezone

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import MountService


GPS_FIX_STATES = frozenset({"fix_2d", "fix_3d"})


class Orchestrator:
    def __init__(self, *, bus: StateBus, mount: MountService) -> None:
        self._bus = bus
        self._mount = mount
        self._synced = False

    async def run(self) -> None:
        async for _event in self._bus.subscribe():
            full = self._bus.get_full_state()
            await self._maybe_sync(full.subsystems)

    async def _maybe_sync(self, subsystems: dict) -> None:
        mount_s = subsystems.get("mount")
        gps_s = subsystems.get("gps")
        if mount_s is None or gps_s is None:
            return

        conditions_met = (
            mount_s.state == "ready" and gps_s.state in GPS_FIX_STATES
        )

        if not conditions_met:
            self._synced = False
            return

        if self._synced:
            return

        lat = gps_s.details.get("lat")
        lon = gps_s.details.get("lon")
        if lat is None or lon is None:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        await self._mount.set_time(now_iso)
        await self._mount.set_location(lat, lon)
        self._synced = True
```

- [ ] **Step 10.4: Run tests and verify pass**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: 4 passed.

- [ ] **Step 10.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(backend): add orchestrator that syncs mount with GPS on boot"
git push
```

---

## Task 11: Application wiring + main.py

**Files:**
- Create: `backend/astro_brain/app.py`
- Create: `backend/astro_brain/main.py`
- Create: `backend/tests/test_app.py`

`build_app()` creates the FastAPI app, instantiates services (fakes by default, real hardware adapters when `ASTRO_BRAIN_HARDWARE=1`), wires the `deps` module, and starts the orchestrator as a background task.

- [ ] **Step 11.1: Write the failing test**

Create `backend/tests/test_app.py`:

```python
from fastapi.testclient import TestClient

from astro_brain.app import build_app


def test_app_starts_with_fakes_and_state_endpoint_responds():
    app = build_app(use_hardware=False)
    with TestClient(app) as client:
        r = client.get("/state")
        assert r.status_code == 200
        body = r.json()
        assert body["subsystems"]["mount"]["state"] == "ready"
        assert body["subsystems"]["gps"]["state"] == "fix_3d"


def test_app_slew_and_stop_flow_end_to_end():
    app = build_app(use_hardware=False)
    with TestClient(app) as client:
        r = client.post(
            "/slew", json={"axis": "alt", "direction": "+", "rate": 4}
        )
        assert r.status_code == 200
        r = client.get("/state")
        assert r.json()["subsystems"]["mount"]["state"] == "moving"
        r = client.post("/stop", json={})
        assert r.status_code == 200
        r = client.get("/state")
        assert r.json()["subsystems"]["mount"]["state"] == "ready"
```

- [ ] **Step 11.2: Run and verify failure**

```bash
pytest tests/test_app.py -v
```

Expected: import error on `astro_brain.app`.

- [ ] **Step 11.3: Implement `app.py`**

Create `backend/astro_brain/app.py`:

```python
"""Application factory — wires services, deps, routes, orchestrator."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from astro_brain import deps
from astro_brain.bus import StateBus
from astro_brain.orchestrator import Orchestrator
from astro_brain.routes.commands import router as commands_router
from astro_brain.routes.events import router as events_router
from astro_brain.routes.state import router as state_router
from astro_brain.services.fakes import (
    FakeGps,
    FakeMount,
    FakeNetwork,
    FakeSystemInfo,
    FakeTracking,
)


def _select_services(bus: StateBus, use_hardware: bool) -> dict:
    if use_hardware:
        from astro_brain.adapters.gpsd_adapter import GpsdAdapter
        from astro_brain.adapters.nexstar_adapter import NexStarMountAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = NexStarMountAdapter(bus)
        gps = GpsdAdapter(bus)
        network = NetworkInfoAdapter(bus)
        system = SystemInfoAdapter(bus)
        tracking = FakeTracking(bus)  # see Task 14; tracking is driven by mount
        return {
            "mount": mount,
            "gps": gps,
            "network": network,
            "system": system,
            "tracking": tracking,
        }
    return {
        "mount": FakeMount(bus),
        "gps": FakeGps(bus),
        "network": FakeNetwork(bus),
        "system": FakeSystemInfo(bus),
        "tracking": FakeTracking(bus),
    }


def build_app(use_hardware: bool | None = None) -> FastAPI:
    if use_hardware is None:
        use_hardware = os.environ.get("ASTRO_BRAIN_HARDWARE", "0") == "1"

    bus = StateBus()
    services = _select_services(bus, use_hardware)
    orchestrator = Orchestrator(bus=bus, mount=services["mount"])

    # wire deps module for routes
    deps.get_bus = lambda: bus
    deps.get_mount = lambda: services["mount"]
    deps.get_tracking = lambda: services["tracking"]
    deps.get_gps = lambda: services["gps"]
    deps.get_network = lambda: services["network"]
    deps.get_system_info = lambda: services["system"]

    background_tasks: list[asyncio.Task] = []

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # start all services (they publish their initial state)
        await services["mount"].start()
        await services["gps"].start()
        await services["network"].start()
        await services["system"].start()
        # orchestrator runs forever, consumes bus events
        orch_task = asyncio.create_task(orchestrator.run(), name="orchestrator")
        background_tasks.append(orch_task)
        try:
            yield
        finally:
            for t in background_tasks:
                t.cancel()
            for t in background_tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            await services["mount"].stop()
            await services["gps"].stop()
            await services["network"].stop()
            await services["system"].stop()

    app = FastAPI(title="Astro-Brain", version="0.1.0", lifespan=lifespan)
    app.include_router(commands_router)
    app.include_router(state_router)
    app.include_router(events_router)
    return app


app = build_app()
```

- [ ] **Step 11.4: Implement `main.py`**

Create `backend/astro_brain/main.py`:

```python
"""CLI entry point: `uvicorn astro_brain.main:app` or `python -m astro_brain.main`."""

from __future__ import annotations

import uvicorn

from astro_brain.app import app  # re-exported for uvicorn


def run() -> None:
    import os

    host = os.environ.get("ASTRO_BRAIN_HOST", "0.0.0.0")
    port = int(os.environ.get("ASTRO_BRAIN_PORT", "8000"))
    uvicorn.run("astro_brain.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
```

- [ ] **Step 11.5: Run all tests and verify pass**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
pytest -v
```

Expected: all tests across all files pass.

**Note:** because `build_app()` conditionally imports the hardware adapters (Task 12–15), those modules don't need to exist for the default fake path to work. Ensure `_select_services(..., use_hardware=True)` is **not** exercised at this stage — it will raise `ImportError` until Tasks 12–15 are complete. That's expected.

- [ ] **Step 11.6: Smoke-run the backend with uvicorn against fakes**

In a separate terminal:

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
uvicorn astro_brain.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/state | python -m json.tool | head -30
curl -s -X POST http://127.0.0.1:8000/slew -H 'content-type: application/json' -d '{"axis":"alt","direction":"+","rate":5}'
curl -s http://127.0.0.1:8000/state | python -m json.tool | head -30
curl -N http://127.0.0.1:8000/events
```

Expected:
- `GET /state` returns a JSON body with all 5 subsystems populated by fakes
- `POST /slew` returns `{"ok":true}` and subsequent `/state` shows `mount.state == "moving"`
- `GET /events` streams `event: snapshot` then `event: update` lines
- Ctrl-C terminates the uvicorn process cleanly

- [ ] **Step 11.7: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/app.py backend/astro_brain/main.py backend/tests/test_app.py
git commit -m "feat(backend): wire application with fakes, orchestrator, and lifecycle"
git push
```

---

## Task 12: Hardware adapter — SystemInfo (`/sys/class/thermal`, `/proc/loadavg`)

This adapter polls `/sys/class/thermal/thermal_zone0/temp` (milli-degrees Celsius) and `/proc/loadavg` every 5 s, and publishes changes to the bus when the state enum transitions.

**Files:**
- Create: `backend/astro_brain/adapters/__init__.py`
- Create: `backend/astro_brain/adapters/system_info.py`

Pure-logic unit tests would need filesystem mocks that add noise — we test integration via manual smoke on the Pi.

- [ ] **Step 12.1: Create the adapters sub-package**

```bash
mkdir -p backend/astro_brain/adapters
touch backend/astro_brain/adapters/__init__.py
```

- [ ] **Step 12.2: Implement the SystemInfo adapter**

Create `backend/astro_brain/adapters/system_info.py`:

```python
"""Reads CPU temperature and load from sysfs/procfs. Pi-native."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState


THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
UPTIME_PATH = Path("/proc/uptime")
LOADAVG_PATH = Path("/proc/loadavg")

POLL_INTERVAL_S = 5.0
WARN_TEMP = 70.0
CRIT_TEMP = 80.0
WARN_LOAD = 1.5


def _read_temp_c() -> float:
    return int(THERMAL_PATH.read_text().strip()) / 1000.0


def _read_uptime_s() -> int:
    return int(float(UPTIME_PATH.read_text().split()[0]))


def _read_loadavg_1min() -> float:
    return float(LOADAVG_PATH.read_text().split()[0])


def _compute_state(cpu_temp_c: float, cpu_load: float) -> str:
    if cpu_temp_c >= CRIT_TEMP:
        return "critical"
    if cpu_temp_c >= WARN_TEMP or cpu_load >= WARN_LOAD:
        return "warning"
    return "ok"


class SystemInfoAdapter:
    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._publish_current()
        self._task = asyncio.create_task(self._loop(), name="system-info-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def _publish_current(self) -> None:
        temp = _read_temp_c()
        load = _read_loadavg_1min()
        uptime = _read_uptime_s()
        state = _compute_state(temp, load)
        self._bus.publish(
            "system",
            SubsystemState(
                state=state,
                details={
                    "cpu_temp_c": temp,
                    "cpu_load": load,
                    "uptime_s": uptime,
                },
                since=datetime.now(timezone.utc),
            ),
        )

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_S)
                self._publish_current()
            except asyncio.CancelledError:
                return
            except Exception:
                # keep the loop alive; state publish will resume next tick
                continue
```

- [ ] **Step 12.3: Verify it imports on the workstation**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
python -c "from astro_brain.adapters.system_info import SystemInfoAdapter; print('ok')"
```

Expected: `ok`. (Reading sysfs files will fail at runtime on non-Linux workstations, but the import must succeed.)

- [ ] **Step 12.4: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/adapters/__init__.py backend/astro_brain/adapters/system_info.py
git commit -m "feat(backend): add SystemInfo adapter (sysfs CPU temp + loadavg)"
git push
```

---

## Task 13: Hardware adapter — NetworkInfo

Reads `/sys/class/net` for active interfaces and runs `iwgetid` to get the SSID. Polls every 5 s and publishes on state/interface/ssid change.

**Files:**
- Create: `backend/astro_brain/adapters/network_info.py`

- [ ] **Step 13.1: Implement the adapter**

Create `backend/astro_brain/adapters/network_info.py`:

```python
"""Reads network state from /sys/class/net and iwgetid. Pi-native."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState


NET_PATH = Path("/sys/class/net")
POLL_INTERVAL_S = 5.0
PRIMARY_INTERFACE = "wlan0"
HOTSPOT_SSID_PREFIX = "astro-brain"


def _interface_is_up(iface: str) -> bool:
    p = NET_PATH / iface / "operstate"
    if not p.exists():
        return False
    return p.read_text().strip() == "up"


def _iface_ip(iface: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "dev", iface], text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        # Example: "3: wlan0    inet 192.168.1.10/24 brd ..."
        parts = line.split()
        if "inet" in parts:
            i = parts.index("inet")
            return parts[i + 1].split("/")[0]
    return None


def _ssid(iface: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["iwgetid", "-r", iface], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.strip() or None


def _compute_network(iface: str) -> tuple[str, dict]:
    if not _interface_is_up(iface):
        return "offline", {"ssid": None, "ip": None}
    ssid = _ssid(iface)
    ip = _iface_ip(iface)
    if ssid and ssid.startswith(HOTSPOT_SSID_PREFIX):
        return "hotspot", {"ssid": ssid, "ip": ip}
    return "client", {"ssid": ssid, "ip": ip}


class NetworkInfoAdapter:
    def __init__(self, bus: StateBus, *, interface: str = PRIMARY_INTERFACE) -> None:
        self._bus = bus
        self._iface = interface
        self._task: asyncio.Task | None = None
        self._last: tuple[str, dict] | None = None

    async def start(self) -> None:
        self._publish_current()
        self._task = asyncio.create_task(self._loop(), name="network-info-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def _publish_current(self) -> None:
        state, details = _compute_network(self._iface)
        if self._last == (state, details):
            return
        self._last = (state, details)
        self._bus.publish(
            "network",
            SubsystemState(
                state=state,
                details=dict(details),
                since=datetime.now(timezone.utc),
            ),
        )

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_S)
                self._publish_current()
            except asyncio.CancelledError:
                return
            except Exception:
                continue
```

- [ ] **Step 13.2: Verify import on workstation**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
python -c "from astro_brain.adapters.network_info import NetworkInfoAdapter; print('ok')"
```

Expected: `ok`.

- [ ] **Step 13.3: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/adapters/network_info.py
git commit -m "feat(backend): add NetworkInfo adapter (sysfs + iwgetid)"
git push
```

---

## Task 14: Hardware adapter — Gpsd (DroTek)

Consumes the gpsd stream via `gpsd-py3`. Publishes `no_fix` / `searching` / `fix_2d` / `fix_3d` based on `mode`. Throttles detail updates to 1 Hz when the enum doesn't change.

Dependency `gpsd-py3` is only installed when `pip install -e '.[hardware]'`. This task's module imports it lazily inside the class constructor so the import on the workstation still succeeds.

**Files:**
- Create: `backend/astro_brain/adapters/gpsd_adapter.py`

- [ ] **Step 14.1: Implement the adapter**

Create `backend/astro_brain/adapters/gpsd_adapter.py`:

```python
"""Consumes gpsd for the DroTek GPS module. Pi-native.

Requires the `gpsd-py3` extra (install with `pip install -e '.[hardware]'`).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from astro_brain.bus import StateBus
from astro_brain.subsystems import SubsystemState


POLL_INTERVAL_S = 0.5
DETAIL_THROTTLE_S = 1.0


def _mode_to_state(mode: int, satellites: int) -> str:
    # gpsd 'mode' values: 0=unknown, 1=no_fix, 2=2d_fix, 3=3d_fix
    if mode == 2:
        return "fix_2d"
    if mode == 3:
        return "fix_3d"
    if satellites > 0:
        return "searching"
    return "no_fix"


class GpsdAdapter:
    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._task: asyncio.Task | None = None
        self._last_state: str | None = None
        self._last_detail_publish: datetime | None = None

    async def start(self) -> None:
        # lazy import — keeps workstation import clean
        import gpsd  # type: ignore[import-not-found]

        gpsd.connect()
        self._bus.publish(
            "gps",
            SubsystemState(state="no_fix", since=datetime.now(timezone.utc)),
        )
        self._task = asyncio.create_task(self._loop(), name="gpsd-loop")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._bus.publish(
            "gps",
            SubsystemState(state="off", since=datetime.now(timezone.utc)),
        )

    async def _loop(self) -> None:
        import gpsd  # type: ignore[import-not-found]

        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_S)
                packet = gpsd.get_current()
                mode = int(getattr(packet, "mode", 0) or 0)
                sats = int(getattr(packet, "sats", 0) or 0)
                state = _mode_to_state(mode, sats)
                details: dict = {"satellites": sats}

                if mode >= 2:
                    try:
                        lat, lon = packet.position()
                        details["lat"] = lat
                        details["lon"] = lon
                    except Exception:
                        pass
                if mode == 3:
                    try:
                        details["altitude_m"] = packet.altitude()
                    except Exception:
                        pass
                hdop = getattr(packet, "hdop", None)
                if hdop is not None:
                    details["hdop"] = float(hdop)

                now = datetime.now(timezone.utc)
                state_changed = state != self._last_state
                detail_ok = (
                    self._last_detail_publish is None
                    or now - self._last_detail_publish >= timedelta(
                        seconds=DETAIL_THROTTLE_S
                    )
                )
                if state_changed or detail_ok:
                    self._bus.publish(
                        "gps",
                        SubsystemState(state=state, details=details, since=now),
                    )
                    self._last_state = state
                    self._last_detail_publish = now
            except asyncio.CancelledError:
                return
            except Exception:
                continue
```

- [ ] **Step 14.2: Verify import on workstation (without the hardware extra)**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
python -c "from astro_brain.adapters.gpsd_adapter import GpsdAdapter; print('ok')"
```

Expected: `ok`. (Calling `.start()` would fail without gpsd, but importing the class does not import gpsd.)

- [ ] **Step 14.3: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/adapters/gpsd_adapter.py
git commit -m "feat(backend): add Gpsd hardware adapter (DroTek, via gpsd-py3)"
git push
```

---

## Task 15: Hardware adapter — NexStar mount (via nexstarpy)

Bridges `MountService` to `nexstarpy`. On the Pi, opens the USB-serial port to the mount's HC port. Exposes `slew`, `stop_slew`, `set_time`, `set_location`, `set_tracking_mode`. Publishes `connecting` → `ready` (or `error`) on `start()`, and `moving` / `ready` as slews come and go. A 2 s watchdog calls `get_version()` to detect disconnects.

Tracking is part of this adapter (it drives the mount). `FakeTracking` on the workstation is kept for symmetry; on the Pi the tracking endpoint is wired to the same adapter (see step 15.4).

**Files:**
- Create: `backend/astro_brain/adapters/nexstar_adapter.py`
- Modify: `backend/astro_brain/app.py` (the `_select_services` block — already written to select this adapter; the modification here is to bind `tracking` to the same instance)

- [ ] **Step 15.1: Implement the adapter**

Create `backend/astro_brain/adapters/nexstar_adapter.py`:

```python
"""NexStar mount adapter. Pi-native.

Wraps nexstarpy. Requires `pip install -e '.[hardware]'`.
Assumes the mount's HC port is connected on /dev/ttyUSB0 (override with
the constructor arg).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.services.interfaces import Axis, Direction
from astro_brain.subsystems import SubsystemState


SERIAL_DEVICE_DEFAULT = "/dev/ttyUSB0"
WATCHDOG_INTERVAL_S = 2.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


class NexStarMountAdapter:
    def __init__(self, bus: StateBus, *, device: str = SERIAL_DEVICE_DEFAULT) -> None:
        self._bus = bus
        self._device = device
        self._client: Any = None  # nexstarpy client
        self._active_slews: list[dict[str, Any]] = []
        self._watchdog_task: asyncio.Task | None = None
        self._firmware_version: str | None = None

    async def start(self) -> None:
        self._bus.publish(
            "mount",
            SubsystemState(state="connecting", since=_now()),
        )
        try:
            import nexstarpy  # type: ignore[import-not-found]

            self._client = nexstarpy.NexStar(self._device)
            self._firmware_version = str(self._client.get_version())
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": self._firmware_version},
                    since=_now(),
                ),
            )
            self._watchdog_task = asyncio.create_task(
                self._watchdog(), name="mount-watchdog"
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="error", message=str(exc), since=_now()
                ),
            )

    async def stop(self) -> None:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except (asyncio.CancelledError, Exception):
                pass
            self._watchdog_task = None
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass
        self._client = None
        self._bus.publish(
            "mount",
            SubsystemState(state="disconnected", since=_now()),
        )

    async def slew(self, axis: Axis, direction: Direction, rate: int) -> None:
        if self._client is None:
            return
        self._active_slews = [s for s in self._active_slews if s["axis"] != axis]
        self._active_slews.append(
            {"axis": axis, "direction": direction, "rate": rate}
        )
        try:
            self._client.slew_fixed(axis, direction, rate)
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
                    "firmware_version": self._firmware_version,
                    "active_slews": list(self._active_slews),
                },
                since=_now(),
            ),
        )

    async def stop_slew(self, axis: Axis | None) -> None:
        if self._client is None:
            return
        try:
            if axis is None:
                for a in ("alt", "az"):
                    self._client.stop_slew(a)
                self._active_slews = []
            else:
                self._client.stop_slew(axis)
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
                    details={"active_slews": list(self._active_slews)},
                    since=_now(),
                ),
            )
        else:
            self._bus.publish(
                "mount",
                SubsystemState(
                    state="ready",
                    details={"firmware_version": self._firmware_version},
                    since=_now(),
                ),
            )

    async def set_time(self, utc_iso: str) -> None:
        if self._client is None:
            return
        dt = datetime.fromisoformat(utc_iso)
        self._client.set_time(
            (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
                0,  # UTC offset in hours
                0,  # DST flag
            )
        )

    async def set_location(self, lat: float, lon: float) -> None:
        if self._client is None:
            return
        self._client.set_location(lat, lon)

    async def set_tracking(self, enabled: bool) -> None:
        if self._client is None:
            return
        try:
            mode = 1 if enabled else 0  # 1 = sidereal, 0 = off (NexStar convention)
            self._client.set_tracking_mode(mode)
            value = "sidereal" if enabled else "off"
            self._bus.publish(
                "tracking", SubsystemState(state=value, since=_now())
            )
        except Exception as exc:
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )

    async def _watchdog(self) -> None:
        while True:
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL_S)
                if self._client is None:
                    return
                self._client.get_version()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self._bus.publish(
                    "mount",
                    SubsystemState(state="error", message=str(exc), since=_now()),
                )
                return
```

**Note on `set_tracking`:** the NexStar protocol's exact mode code for sidereal may differ between firmware versions (`1` for sidereal, `2` for lunar, `3` for solar is the most common mapping; verify on the Pi before going further — see Task 17). Adjust the constant here if needed once you confirm on real hardware.

- [ ] **Step 15.2: Update `app.py` to use the adapter as both mount and tracking service**

Open `backend/astro_brain/app.py` and modify the hardware branch inside `_select_services`:

```python
def _select_services(bus: StateBus, use_hardware: bool) -> dict:
    if use_hardware:
        from astro_brain.adapters.gpsd_adapter import GpsdAdapter
        from astro_brain.adapters.nexstar_adapter import NexStarMountAdapter
        from astro_brain.adapters.network_info import NetworkInfoAdapter
        from astro_brain.adapters.system_info import SystemInfoAdapter

        mount = NexStarMountAdapter(bus)
        gps = GpsdAdapter(bus)
        network = NetworkInfoAdapter(bus)
        system = SystemInfoAdapter(bus)
        # mount also implements set_tracking -> re-use it as tracking service
        tracking = mount  # type: ignore[assignment]
        return {
            "mount": mount,
            "gps": gps,
            "network": network,
            "system": system,
            "tracking": tracking,
        }
    return {
        "mount": FakeMount(bus),
        "gps": FakeGps(bus),
        "network": FakeNetwork(bus),
        "system": FakeSystemInfo(bus),
        "tracking": FakeTracking(bus),
    }
```

- [ ] **Step 15.3: Verify all tests still pass on the workstation**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend
source .venv/bin/activate
pytest -v
```

Expected: no regressions — hardware path is not exercised by default.

- [ ] **Step 15.4: Verify module import is clean**

```bash
python -c "from astro_brain.adapters.nexstar_adapter import NexStarMountAdapter; print('ok')"
```

Expected: `ok`.

- [ ] **Step 15.5: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/astro_brain/adapters/nexstar_adapter.py backend/astro_brain/app.py
git commit -m "feat(backend): add NexStar mount adapter and wire it as tracking service"
git push
```

---

## Task 16: Deployment — systemd unit + install script

**Files:**
- Create: `backend/deploy/astro-brain.service`
- Create: `backend/deploy/install.sh`

- [ ] **Step 16.1: Write the systemd unit**

Create `backend/deploy/astro-brain.service`:

```ini
[Unit]
Description=Astro-Brain backend (FastAPI)
After=network-online.target gpsd.service
Wants=network-online.target

[Service]
Type=simple
User=pascal3100
WorkingDirectory=/home/pascal3100/code/astro-brain/backend
Environment="ASTRO_BRAIN_HARDWARE=1"
Environment="ASTRO_BRAIN_HOST=0.0.0.0"
Environment="ASTRO_BRAIN_PORT=8000"
ExecStart=/home/pascal3100/code/astro-brain/backend/.venv/bin/uvicorn \
    astro_brain.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 16.2: Write the install script**

Create `backend/deploy/install.sh`:

```bash
#!/usr/bin/env bash
# Install / update the astro-brain systemd service on the Pi.
# Run from the backend/ directory on the Pi.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

if [[ ! -d .venv ]]; then
  echo "Creating venv..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[hardware,dev]'

echo "Installing systemd unit..."
sudo cp deploy/astro-brain.service /etc/systemd/system/astro-brain.service
sudo systemctl daemon-reload
sudo systemctl enable astro-brain.service
sudo systemctl restart astro-brain.service

echo "Status:"
sudo systemctl --no-pager status astro-brain.service || true
```

Make it executable:

```bash
chmod +x backend/deploy/install.sh
```

- [ ] **Step 16.3: Push and sync the Pi**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/deploy/
git commit -m "feat(backend): add systemd unit and install script"
git push

ssh astro-brain 'cd ~/code/astro-brain && git pull'
```

- [ ] **Step 16.4: Run the install script on the Pi**

```bash
ssh astro-brain 'cd ~/code/astro-brain/backend && bash deploy/install.sh'
```

Expected: venv is created at `~/code/astro-brain/backend/.venv`, dependencies install, the systemd unit starts and shows `active (running)`.

- [ ] **Step 16.5: Smoke-test the live service from the workstation**

```bash
curl -s http://astro-brain.local:8000/state | python -m json.tool | head -40
```

Expected: real state with `mount.state` reflecting actual hardware (likely `ready` if the mount is powered on and connected, `error` otherwise).

- [ ] **Step 16.6: Commit**

(No new files to commit — Step 16.3 already committed. This step exists so the executor doesn't skip the sync-Pi path.)

---

## Task 17: Manual hardware integration checklist

The backend is now running on the Pi with real hardware adapters. This task is a *manual checklist* — not automated tests. Document the findings in `backend/deploy/INTEGRATION_CHECKLIST.md`.

**Files:**
- Create: `backend/deploy/INTEGRATION_CHECKLIST.md`

- [ ] **Step 17.1: Create the checklist document**

Create `backend/deploy/INTEGRATION_CHECKLIST.md`:

```markdown
# Backend v0.1 — Manual Integration Checklist

Run once the service is deployed on the Pi with `ASTRO_BRAIN_HARDWARE=1`.

## Service health

- [ ] `sudo systemctl status astro-brain.service` shows `active (running)`
- [ ] `journalctl -u astro-brain.service -n 50 --no-pager` shows no repeated tracebacks

## Baseline REST endpoints

- [ ] `curl http://astro-brain.local:8000/state` returns 200 with all 5 subsystems
- [ ] `curl -N http://astro-brain.local:8000/events` streams an `event: snapshot` then an update within 5 s (from system-info polling)

## Mount — smoke test

Prerequisite: the mount is powered on and connected via USB-serial on `/dev/ttyUSB0`.

- [ ] On boot, `mount` subsystem reaches `ready` with a non-null `firmware_version`
- [ ] `POST /slew {"axis":"alt","direction":"+","rate":1}` starts a visible slow slew
- [ ] `POST /stop {}` halts the slew
- [ ] `POST /tracking {"enabled":true}` enables sidereal tracking (observe the RA drive engages)
- [ ] `POST /tracking {"enabled":false}` disables it
- [ ] Disconnecting the USB cable briefly causes `mount` to transition to `error`; reconnecting lets a `systemctl restart astro-brain` recover to `ready`

**If sidereal tracking does NOT engage**, the mode constant in `set_tracking` (NexStarMountAdapter) is wrong for this firmware. Try: 1 → sidereal, then 2, then 3. Update the code once the correct value is identified.

## GPS — smoke test

Prerequisite: DroTek GPS is plugged in and `sudo systemctl start gpsd` succeeded. `cgps -s` shows a fix in a window of open sky.

- [ ] On service start, `gps` subsystem reaches at least `searching` within 5 s
- [ ] Outdoors (or with a clear window), `gps` reaches `fix_3d` within a few minutes
- [ ] Details contain `lat`, `lon`, `satellites`, `hdop`
- [ ] Once both `mount.ready` AND `gps.fix_3d` hold, the orchestrator logs show `set_time` + `set_location` were called exactly once (add a `logging.info` in `orchestrator._maybe_sync` if this isn't already visible)

## Network — smoke test

- [ ] With the Pi connected to the home Wi-Fi: `network.state == "client"`, `details.ssid` matches the home SSID, `details.ip` matches `ip a show wlan0`
- [ ] Disconnecting Wi-Fi (e.g. `sudo ip link set wlan0 down`) brings `network.state` to `offline` within 5 s

## System — smoke test

- [ ] `system.state == "ok"` at idle (CPU temp < 70°C, load < 1.5)
- [ ] Running `stress-ng --cpu 4 --timeout 60` drives `system.state` to `warning`; the transition propagates to `overall = "orange"` within 5 s

## Overall state

- [ ] With everything nominal: `overall = "green"`
- [ ] With mount disconnected: `overall = "red"`
- [ ] With GPS searching only: `overall = "blue"`

## Findings

Record any discrepancies, surprising behaviors, or adjustments needed below:

- <fill in during the run>
```

- [ ] **Step 17.2: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add backend/deploy/INTEGRATION_CHECKLIST.md
git commit -m "docs(backend): add manual hardware integration checklist"
git push
```

- [ ] **Step 17.3: Walk through the checklist on the Pi**

This is a physical test session. SSH to the Pi, plug in the mount and the GPS, and tick each box in `INTEGRATION_CHECKLIST.md`. Open issues and fix them as regular bug-fix commits (outside the scope of this plan).

---

## Plan complete

At the end of Task 17, the Pi is running a backend that:
- exposes `/state`, `/slew`, `/stop`, `/tracking`, `/events`
- publishes real-time subsystem state via SSE
- synchronizes the mount with GPS + time on boot
- is supervised by systemd and restarts on failure

The Flutter app (Plan 2) can now be built and pointed at `http://astro-brain.local:8000`.
