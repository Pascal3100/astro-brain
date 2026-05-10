# Catalogue backend — tranche A (stars étendues) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer la première tranche du catalogue backend Macro 3 #4 — table sqlite unifiée `catalog_objects`, abstraction `CatalogProvider` extensible, seed pipeline workstation→`.sql` committé→boot apply, endpoint REST `/catalog/objects` exposant ~100-150 étoiles brillantes nommées (IAU CSN cap mag ≤ 3).

**Architecture:** Migration `_003_catalog_objects` ajoute la table `catalog_objects` (discriminateur `kind`). `SqliteCatalogProvider(db, kind="star")` lit cette table, dispatch via `CatalogRegistry`. Au boot, `seed_runner.apply_seeds(db, data_dir)` applique tous les `seed_*.sql` du package data via `executescript` (idempotent grâce à `INSERT OR REPLACE`). Un script dev `tools/seed_stars.py` régénère `seed_stars.sql` à partir du CSV IAU. Endpoint `GET /catalog/objects` accepte `kind / search / max_mag / limit / offset`.

**Tech Stack:** FastAPI, aiosqlite, Pydantic v2, importlib.resources, pytest-asyncio. Pas de nouvelle dep externe (le pull IAU se fait via `urllib` stdlib dans le tool dev).

Spec : [`docs/superpowers/specs/2026-05-10-catalog-backend-stars-design.md`](../specs/2026-05-10-catalog-backend-stars-design.md).

---

## File Structure

### Created

- `backend/astro_brain/repository/migrations/_003_catalog_objects.py` — DDL `catalog_objects` + index.
- `backend/astro_brain/services/catalog/__init__.py` — package marker (vide).
- `backend/astro_brain/services/catalog/models.py` — Pydantic `CatalogObject` + `CatalogFilter`.
- `backend/astro_brain/services/catalog/providers.py` — `CatalogProvider` Protocol + `SqliteCatalogProvider`.
- `backend/astro_brain/services/catalog/registry.py` — `CatalogRegistry` (dispatch par kind).
- `backend/astro_brain/services/catalog/seed_runner.py` — `apply_seeds(db, data_dir)`.
- `backend/astro_brain/data/__init__.py` — package marker (vide, permet `importlib.resources.files`).
- `backend/astro_brain/data/seed_stars.sql` — seed généré (committé).
- `backend/astro_brain/routes/catalog.py` — router `/catalog/objects`.
- `backend/tools/seed_stars.py` — script dev workstation pull IAU CSV → `.sql`.
- `backend/tests/test_catalog_models.py`
- `backend/tests/test_catalog_sqlite_provider.py`
- `backend/tests/test_catalog_registry.py`
- `backend/tests/test_catalog_seed_runner.py`
- `backend/tests/test_catalog_routes.py`
- `backend/tests/test_catalog_seed_stars_smoke.py`
- `backend/tests/test_seed_stars_tool.py` — tests offline du tool dev (avec CSV fixture local).

### Modified

- `backend/astro_brain/app.py` — lifespan : crée registry + apply_seeds, expose `app.state.catalog_registry` ; `app.include_router(catalog_router)`.
- `backend/astro_brain/deps.py` — ajout `get_catalog_registry`.
- `backend/tests/test_state_db.py` — étend les assertions à `version == 3` + table `catalog_objects`.

---

## Task 1: Migration `_003_catalog_objects`

**Files:**
- Create: `backend/astro_brain/repository/migrations/_003_catalog_objects.py`
- Modify: `backend/tests/test_state_db.py`

- [ ] **Step 1: Write the failing test**

Modify `backend/tests/test_state_db.py` — bump expected version + assert new table:

```python
async def test_run_migrations_creates_schema(db: aiosqlite.Connection) -> None:
    version = await run_migrations(db)
    assert version == 3

    tables = await _table_names(db)
    assert {
        "schema_version",
        "calibration_sensor",
        "mount_limits",
        "alignment_model",
        "catalog_objects",
    }.issubset(tables)

    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 3


async def test_run_migrations_is_idempotent(db: aiosqlite.Connection) -> None:
    first = await run_migrations(db)
    second = await run_migrations(db)
    assert first == 3
    assert second == 3

    tables = await _table_names(db)
    assert {
        "schema_version",
        "calibration_sensor",
        "mount_limits",
        "alignment_model",
        "catalog_objects",
    }.issubset(tables)

    cursor = await db.execute("SELECT COUNT(*) FROM schema_version WHERE version = 3")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == 1


async def test_catalog_objects_indexes_present(db: aiosqlite.Connection) -> None:
    await run_migrations(db)
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='catalog_objects'"
    )
    rows = await cursor.fetchall()
    await cursor.close()
    names = {row[0] for row in rows}
    assert {"idx_catalog_kind", "idx_catalog_name", "idx_catalog_mag"}.issubset(names)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_state_db.py -v`
Expected: FAIL — version still 2, `catalog_objects` table missing.

- [ ] **Step 3: Create the migration module**

Create `backend/astro_brain/repository/migrations/_003_catalog_objects.py`:

```python
"""Catalogue d'objets célestes — table unifiée `catalog_objects`.

Discriminée par `kind` (star, messier, ngc, …). En tranche A, seed `kind='star'`
uniquement (~100-150 IAU named stars cap mag ≤ 3). Voir spec
docs/superpowers/specs/2026-05-10-catalog-backend-stars-design.md.
"""
from __future__ import annotations

VERSION = 3

SQL = """
CREATE TABLE IF NOT EXISTS catalog_objects (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    designation TEXT,
    ra_deg REAL NOT NULL,
    dec_deg REAL NOT NULL,
    mag REAL,
    constellation TEXT,
    object_type TEXT,
    angular_size_arcmin REAL,
    extras_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_catalog_kind ON catalog_objects(kind);
CREATE INDEX IF NOT EXISTS idx_catalog_name ON catalog_objects(name);
CREATE INDEX IF NOT EXISTS idx_catalog_mag ON catalog_objects(mag);
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_state_db.py -v`
Expected: PASS — 5/5 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/repository/migrations/_003_catalog_objects.py backend/tests/test_state_db.py
git commit -m "feat(backend): migration _003_catalog_objects (catalogue table unifiée)"
```

---

## Task 2: Pydantic models `CatalogObject` + `CatalogFilter`

**Files:**
- Create: `backend/astro_brain/services/catalog/__init__.py`
- Create: `backend/astro_brain/services/catalog/models.py`
- Create: `backend/tests/test_catalog_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_catalog_models.py`:

```python
"""Tests for the catalog Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject


def test_catalog_object_minimal_fields() -> None:
    obj = CatalogObject(
        qualified_id="star:sirius",
        kind="star",
        name="Sirius",
        ra_deg=101.287,
        dec_deg=-16.716,
    )
    assert obj.qualified_id == "star:sirius"
    assert obj.kind == "star"
    assert obj.designation is None
    assert obj.mag is None
    assert obj.constellation is None
    assert obj.extras == {}


def test_catalog_object_full_fields() -> None:
    obj = CatalogObject(
        qualified_id="messier:m31",
        kind="messier",
        name="Andromeda Galaxy",
        designation="M 31",
        ra_deg=10.6847,
        dec_deg=41.269,
        mag=3.4,
        constellation="Andromeda",
        object_type="galaxy",
        angular_size_arcmin=178.0,
        extras={"distance_kly": 2540},
    )
    assert obj.designation == "M 31"
    assert obj.object_type == "galaxy"
    assert obj.extras == {"distance_kly": 2540}


def test_catalog_object_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        CatalogObject(
            qualified_id="foo:x",
            kind="foo",  # type: ignore[arg-type]
            name="X",
            ra_deg=0.0,
            dec_deg=0.0,
        )


def test_catalog_filter_defaults() -> None:
    f = CatalogFilter()
    assert f.kind is None
    assert f.search is None
    assert f.max_mag is None
    assert f.limit == 100
    assert f.offset == 0


def test_catalog_filter_limit_max_500() -> None:
    f = CatalogFilter(limit=500)
    assert f.limit == 500
    with pytest.raises(ValidationError):
        CatalogFilter(limit=501)


def test_catalog_filter_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CatalogFilter(limit=0)


def test_catalog_filter_offset_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        CatalogFilter(offset=-1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_models.py -v`
Expected: FAIL — module `astro_brain.services.catalog.models` not found.

- [ ] **Step 3: Create package marker + models**

Create `backend/astro_brain/services/catalog/__init__.py`:

```python
"""Catalogue d'objets célestes — providers, registry, seed runner."""
```

Create `backend/astro_brain/services/catalog/models.py`:

```python
"""Pydantic models for the unified catalogue."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CatalogKind = Literal["star", "messier", "planet", "comet"]


class CatalogObject(BaseModel):
    """One celestial object served by the catalogue layer."""

    qualified_id: str
    kind: CatalogKind
    name: str
    designation: str | None = None
    ra_deg: float
    dec_deg: float
    mag: float | None = None
    constellation: str | None = None
    object_type: str | None = None
    angular_size_arcmin: float | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class CatalogFilter(BaseModel):
    """Server-side filters for `GET /catalog/objects`."""

    kind: str | None = None
    search: str | None = None
    max_mag: float | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_models.py -v`
Expected: PASS — 7/7.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/__init__.py backend/astro_brain/services/catalog/models.py backend/tests/test_catalog_models.py
git commit -m "feat(backend): catalog Pydantic models (CatalogObject + CatalogFilter)"
```

---

## Task 3: `SqliteCatalogProvider`

**Files:**
- Create: `backend/astro_brain/services/catalog/providers.py`
- Create: `backend/tests/test_catalog_sqlite_provider.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_catalog_sqlite_provider.py`:

```python
"""Tests for SqliteCatalogProvider."""
from __future__ import annotations

from collections.abc import AsyncIterator

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import SqliteCatalogProvider


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        yield conn
    finally:
        await conn.close()


async def _insert(
    db: aiosqlite.Connection,
    *,
    qid: str,
    kind: str,
    name: str,
    designation: str | None = None,
    ra: float = 0.0,
    dec: float = 0.0,
    mag: float | None = None,
    constellation: str | None = None,
    object_type: str | None = None,
    angular_size_arcmin: float | None = None,
    extras_json: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO catalog_objects "
        "(id, kind, name, designation, ra_deg, dec_deg, mag, constellation, "
        "object_type, angular_size_arcmin, extras_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (qid, kind, name, designation, ra, dec, mag, constellation,
         object_type, angular_size_arcmin, extras_json),
    )
    await db.commit()


async def test_list_objects_filters_by_kind(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    await _insert(db, qid="messier:m31", kind="messier", name="Andromeda", mag=3.4)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter())

    assert len(rows) == 1
    assert rows[0].qualified_id == "star:sirius"
    assert rows[0].kind == "star"


async def test_list_objects_filters_by_max_mag(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    await _insert(db, qid="star:vega", kind="star", name="Vega", mag=0.03)
    await _insert(db, qid="star:dim", kind="star", name="Dim", mag=4.5)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter(max_mag=1.0))

    names = {r.name for r in rows}
    assert names == {"Sirius", "Vega"}


async def test_list_objects_filters_by_search_on_name_and_designation(
    db: aiosqlite.Connection,
) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius",
                  designation="α CMa", mag=-1.46)
    await _insert(db, qid="star:rigel", kind="star", name="Rigel",
                  designation="β Ori", mag=0.13)
    provider = SqliteCatalogProvider(db, kind="star")

    by_name = await provider.list_objects(CatalogFilter(search="rig"))
    assert {r.name for r in by_name} == {"Rigel"}

    by_designation = await provider.list_objects(CatalogFilter(search="CMa"))
    assert {r.name for r in by_designation} == {"Sirius"}


async def test_list_objects_orders_by_mag_then_name(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:b", kind="star", name="B", mag=2.0)
    await _insert(db, qid="star:a", kind="star", name="A", mag=2.0)
    await _insert(db, qid="star:c", kind="star", name="C", mag=1.0)
    await _insert(db, qid="star:nullmag", kind="star", name="NullMag", mag=None)
    provider = SqliteCatalogProvider(db, kind="star")

    rows = await provider.list_objects(CatalogFilter())

    # mag asc (NULLS LAST), then name asc
    assert [r.name for r in rows] == ["C", "A", "B", "NullMag"]


async def test_list_objects_limit_offset(db: aiosqlite.Connection) -> None:
    for i in range(5):
        await _insert(db, qid=f"star:s{i}", kind="star", name=f"S{i}", mag=float(i))
    provider = SqliteCatalogProvider(db, kind="star")

    page1 = await provider.list_objects(CatalogFilter(limit=2, offset=0))
    page2 = await provider.list_objects(CatalogFilter(limit=2, offset=2))

    assert [r.name for r in page1] == ["S0", "S1"]
    assert [r.name for r in page2] == ["S2", "S3"]


async def test_get_object_strips_kind_prefix(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.qualified_id == "star:sirius"
    assert obj.name == "Sirius"


async def test_get_object_returns_none_when_absent(db: aiosqlite.Connection) -> None:
    provider = SqliteCatalogProvider(db, kind="star")
    assert await provider.get_object("missing") is None


async def test_get_object_does_not_cross_kind(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="messier:m31", kind="messier", name="Andromeda", mag=3.4)
    provider = SqliteCatalogProvider(db, kind="star")

    assert await provider.get_object("m31") is None


async def test_extras_json_parsed_to_dict(db: aiosqlite.Connection) -> None:
    await _insert(
        db,
        qid="star:sirius",
        kind="star",
        name="Sirius",
        mag=-1.46,
        extras_json='{"spectral_type": "A1V"}',
    )
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.extras == {"spectral_type": "A1V"}


async def test_extras_json_null_yields_empty_dict(db: aiosqlite.Connection) -> None:
    await _insert(db, qid="star:sirius", kind="star", name="Sirius", mag=-1.46)
    provider = SqliteCatalogProvider(db, kind="star")

    obj = await provider.get_object("sirius")

    assert obj is not None
    assert obj.extras == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_sqlite_provider.py -v`
Expected: FAIL — `SqliteCatalogProvider` not defined.

- [ ] **Step 3: Implement the provider**

Create `backend/astro_brain/services/catalog/providers.py`:

```python
"""Catalog providers — abstraction + sqlite-backed implementation."""
from __future__ import annotations

import json
from typing import Any, Protocol

import aiosqlite

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject

_SELECT_COLUMNS = (
    "id, kind, name, designation, ra_deg, dec_deg, mag, "
    "constellation, object_type, angular_size_arcmin, extras_json"
)


def _row_to_object(row: tuple[Any, ...]) -> CatalogObject:
    (
        qid,
        kind,
        name,
        designation,
        ra_deg,
        dec_deg,
        mag,
        constellation,
        object_type,
        angular_size_arcmin,
        extras_json,
    ) = row
    extras: dict[str, Any] = {}
    if extras_json:
        extras = json.loads(extras_json)
    return CatalogObject(
        qualified_id=qid,
        kind=kind,
        name=name,
        designation=designation,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        mag=mag,
        constellation=constellation,
        object_type=object_type,
        angular_size_arcmin=angular_size_arcmin,
        extras=extras,
    )


class CatalogProvider(Protocol):
    """A source of CatalogObjects for one specific kind."""

    kind: str

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        ...

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        ...


class SqliteCatalogProvider:
    """Reads from `catalog_objects` rows whose `kind` matches `self.kind`."""

    def __init__(self, db: aiosqlite.Connection, *, kind: str) -> None:
        self._db = db
        self.kind = kind

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        sql = f"SELECT {_SELECT_COLUMNS} FROM catalog_objects WHERE kind = ?"
        params: list[Any] = [self.kind]

        if filter.max_mag is not None:
            sql += " AND mag IS NOT NULL AND mag <= ?"
            params.append(filter.max_mag)

        if filter.search:
            like = f"%{filter.search}%"
            sql += " AND (name LIKE ? OR designation LIKE ?)"
            params.extend([like, like])

        sql += (
            " ORDER BY CASE WHEN mag IS NULL THEN 1 ELSE 0 END, mag, name"
            " LIMIT ? OFFSET ?"
        )
        params.extend([filter.limit, filter.offset])

        cursor = await self._db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        await cursor.close()
        return [_row_to_object(row) for row in rows]

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        qid = f"{self.kind}:{raw_id}"
        cursor = await self._db.execute(
            f"SELECT {_SELECT_COLUMNS} FROM catalog_objects WHERE id = ?",
            (qid,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return _row_to_object(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_sqlite_provider.py -v`
Expected: PASS — 10/10.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/providers.py backend/tests/test_catalog_sqlite_provider.py
git commit -m "feat(backend): SqliteCatalogProvider with kind/search/max_mag filters"
```

---

## Task 4: `CatalogRegistry`

**Files:**
- Create: `backend/astro_brain/services/catalog/registry.py`
- Create: `backend/tests/test_catalog_registry.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_catalog_registry.py`:

```python
"""Tests for CatalogRegistry dispatch logic."""
from __future__ import annotations

import pytest

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.registry import CatalogRegistry


class _FakeProvider:
    def __init__(self, kind: str, objects: list[CatalogObject]) -> None:
        self.kind = kind
        self._objects = objects
        self.list_calls: list[CatalogFilter] = []

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        self.list_calls.append(filter)
        results = list(self._objects)
        if filter.max_mag is not None:
            results = [o for o in results if o.mag is not None and o.mag <= filter.max_mag]
        return results[filter.offset : filter.offset + filter.limit]

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        for obj in self._objects:
            if obj.qualified_id.split(":", 1)[1] == raw_id:
                return obj
        return None


def _star(qid: str, name: str, mag: float | None) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid,
        kind=qid.split(":", 1)[0],  # type: ignore[arg-type]
        name=name,
        ra_deg=0.0,
        dec_deg=0.0,
        mag=mag,
    )


@pytest.mark.asyncio
async def test_list_all_dispatches_by_kind() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    messier = _FakeProvider("messier", [_star("messier:m31", "Andromeda", 3.4)])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    rows = await reg.list_all(CatalogFilter(kind="star"))

    assert [r.qualified_id for r in rows] == ["star:sirius"]
    assert messier.list_calls == []


@pytest.mark.asyncio
async def test_list_all_unknown_kind_returns_empty() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    rows = await reg.list_all(CatalogFilter(kind="ngc"))

    assert rows == []


@pytest.mark.asyncio
async def test_list_all_no_kind_merges_all_providers_and_sorts_by_mag() -> None:
    stars = _FakeProvider("star", [
        _star("star:sirius", "Sirius", -1.46),
        _star("star:vega", "Vega", 0.03),
    ])
    messier = _FakeProvider("messier", [_star("messier:m31", "Andromeda", 3.4)])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    rows = await reg.list_all(CatalogFilter(limit=10))

    assert [r.name for r in rows] == ["Sirius", "Vega", "Andromeda"]


@pytest.mark.asyncio
async def test_list_all_no_kind_paginates_globally() -> None:
    stars = _FakeProvider("star", [
        _star("star:s1", "S1", 1.0),
        _star("star:s2", "S2", 2.0),
    ])
    messier = _FakeProvider("messier", [
        _star("messier:m1", "M1", 1.5),
        _star("messier:m2", "M2", 2.5),
    ])
    reg = CatalogRegistry({"star": stars, "messier": messier})

    page1 = await reg.list_all(CatalogFilter(limit=2, offset=0))
    page2 = await reg.list_all(CatalogFilter(limit=2, offset=2))

    assert [r.name for r in page1] == ["S1", "M1"]
    assert [r.name for r in page2] == ["S2", "M2"]


@pytest.mark.asyncio
async def test_get_by_qualified_id_dispatches() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    reg = CatalogRegistry({"star": stars})

    obj = await reg.get_by_qualified_id("star:sirius")

    assert obj is not None
    assert obj.name == "Sirius"


@pytest.mark.asyncio
async def test_get_by_qualified_id_invalid_format_returns_none() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    assert await reg.get_by_qualified_id("noprefix") is None


@pytest.mark.asyncio
async def test_get_by_qualified_id_unknown_kind_returns_none() -> None:
    reg = CatalogRegistry({"star": _FakeProvider("star", [])})

    assert await reg.get_by_qualified_id("ngc:7000") is None


@pytest.mark.asyncio
async def test_get_by_qualified_id_unknown_id_returns_none() -> None:
    stars = _FakeProvider("star", [_star("star:sirius", "Sirius", -1.46)])
    reg = CatalogRegistry({"star": stars})

    assert await reg.get_by_qualified_id("star:missing") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_registry.py -v`
Expected: FAIL — `CatalogRegistry` not defined.

- [ ] **Step 3: Implement the registry**

Create `backend/astro_brain/services/catalog/registry.py`:

```python
"""CatalogRegistry — dispatch list/get queries to the appropriate provider."""
from __future__ import annotations

from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.providers import CatalogProvider


class CatalogRegistry:
    """Dispatch facade in front of one or more providers keyed by `kind`."""

    def __init__(self, providers: dict[str, CatalogProvider]) -> None:
        self._providers = providers

    async def list_all(self, filter: CatalogFilter) -> list[CatalogObject]:
        if filter.kind is not None:
            provider = self._providers.get(filter.kind)
            if provider is None:
                return []
            return await provider.list_objects(filter)

        # Sans filtre kind : interroger tous les providers, fusionner, paginer.
        merged: list[CatalogObject] = []
        widened = filter.model_copy(
            update={"limit": filter.limit + filter.offset, "offset": 0}
        )
        for provider in self._providers.values():
            merged.extend(await provider.list_objects(widened))
        merged.sort(
            key=lambda o: (o.mag if o.mag is not None else float("inf"), o.name)
        )
        return merged[filter.offset : filter.offset + filter.limit]

    async def get_by_qualified_id(self, qid: str) -> CatalogObject | None:
        if ":" not in qid:
            return None
        kind, raw_id = qid.split(":", 1)
        provider = self._providers.get(kind)
        if provider is None:
            return None
        return await provider.get_object(raw_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_registry.py -v`
Expected: PASS — 8/8.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/registry.py backend/tests/test_catalog_registry.py
git commit -m "feat(backend): CatalogRegistry dispatch by kind with global pagination"
```

---

## Task 5: Seed runner (`apply_seeds`)

**Files:**
- Create: `backend/astro_brain/services/catalog/seed_runner.py`
- Create: `backend/astro_brain/data/__init__.py`
- Create: `backend/tests/test_catalog_seed_runner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_catalog_seed_runner.py`:

```python
"""Tests for catalog seed_runner.apply_seeds."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.seed_runner import apply_seeds


@pytest.fixture
async def db() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        yield conn
    finally:
        await conn.close()


def _write_seed(dir: Path, name: str, body: str) -> Path:
    path = dir / name
    path.write_text(body, encoding="utf-8")
    return path


async def _count(db: aiosqlite.Connection, kind: str) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) FROM catalog_objects WHERE kind = ?", (kind,)
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    return int(row[0])


async def test_apply_seeds_loads_inserts(tmp_path: Path, db: aiosqlite.Connection) -> None:
    _write_seed(
        tmp_path,
        "seed_stars.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
    )

    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 1


async def test_apply_seeds_idempotent_via_insert_or_replace(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    _write_seed(
        tmp_path,
        "seed_stars.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
    )

    await apply_seeds(db, tmp_path)
    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 1


async def test_apply_seeds_replaces_updated_row(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    seed = tmp_path / "seed_stars.sql"
    seed.write_text(
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.46);\n",
        encoding="utf-8",
    )
    await apply_seeds(db, tmp_path)

    seed.write_text(
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:sirius', 'star', 'Sirius', 101.287, -16.716, -1.50);\n",
        encoding="utf-8",
    )
    await apply_seeds(db, tmp_path)

    cursor = await db.execute(
        "SELECT mag FROM catalog_objects WHERE id = 'star:sirius'"
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] == pytest.approx(-1.50)


async def test_apply_seeds_missing_dir_is_noop(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    missing = tmp_path / "does_not_exist"

    await apply_seeds(db, missing)

    assert await _count(db, "star") == 0


async def test_apply_seeds_no_matching_files_is_noop(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    (tmp_path / "not_a_seed.txt").write_text("garbage", encoding="utf-8")

    await apply_seeds(db, tmp_path)

    assert await _count(db, "star") == 0


async def test_apply_seeds_logs_and_continues_on_broken_seed(
    tmp_path: Path,
    db: aiosqlite.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_seed(tmp_path, "seed_a_broken.sql", "THIS IS NOT VALID SQL;\n")
    _write_seed(
        tmp_path,
        "seed_b_ok.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:vega', 'star', 'Vega', 279.235, 38.784, 0.03);\n",
    )

    with caplog.at_level(logging.ERROR):
        await apply_seeds(db, tmp_path)

    assert any("seed_a_broken.sql" in rec.message for rec in caplog.records)
    assert await _count(db, "star") == 1


async def test_apply_seeds_processes_files_in_lexical_order(
    tmp_path: Path, db: aiosqlite.Connection
) -> None:
    _write_seed(
        tmp_path,
        "seed_b.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:x', 'star', 'X', 0, 0, 1.0);\n",
    )
    _write_seed(
        tmp_path,
        "seed_a.sql",
        "INSERT OR REPLACE INTO catalog_objects "
        "(id, kind, name, ra_deg, dec_deg, mag) "
        "VALUES ('star:x', 'star', 'X', 0, 0, 9.99);\n",
    )

    await apply_seeds(db, tmp_path)

    cursor = await db.execute("SELECT mag FROM catalog_objects WHERE id = 'star:x'")
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    # seed_a runs first, seed_b last → final value from seed_b
    assert row[0] == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_seed_runner.py -v`
Expected: FAIL — module `astro_brain.services.catalog.seed_runner` not found.

- [ ] **Step 3: Create data package marker + seed runner**

Create `backend/astro_brain/data/__init__.py`:

```python
"""Embedded data files (seeds, BSP, …) shipped with the backend package."""
```

Create `backend/astro_brain/services/catalog/seed_runner.py`:

```python
"""Apply `seed_*.sql` files from a data directory at boot, idempotently."""
from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


async def apply_seeds(db: aiosqlite.Connection, data_dir: Path) -> None:
    """Run every `seed_*.sql` under ``data_dir`` against ``db``.

    Idempotent par construction (les seeds utilisent `INSERT OR REPLACE`).
    Une seed cassée logge l'erreur et n'interrompt pas le boot — un Pi sans
    catalogue est dégradé mais reste manœuvrable.
    """
    if not data_dir.is_dir():
        return

    for sql_path in sorted(data_dir.glob("seed_*.sql")):
        sql = sql_path.read_text(encoding="utf-8")
        try:
            await db.executescript(sql)
            await db.commit()
        except Exception:
            logger.exception("catalog seed failed: %s", sql_path.name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_seed_runner.py -v`
Expected: PASS — 7/7.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/seed_runner.py backend/astro_brain/data/__init__.py backend/tests/test_catalog_seed_runner.py
git commit -m "feat(backend): catalog seed_runner.apply_seeds (idempotent + log-and-continue)"
```

---

## Task 6: REST router `/catalog/objects`

**Files:**
- Create: `backend/astro_brain/routes/catalog.py`
- Create: `backend/tests/test_catalog_routes.py`
- Modify: `backend/astro_brain/deps.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_catalog_routes.py`:

```python
"""Tests for /catalog/objects routes."""
from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.routes.catalog import router
from astro_brain.services.catalog.models import CatalogObject


def _build_client(registry) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.catalog_registry = registry
    return TestClient(app)


def _star(qid: str, name: str, mag: float | None = 1.0) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid,
        kind="star",
        name=name,
        ra_deg=0.0,
        dec_deg=0.0,
        mag=mag,
    )


def test_list_objects_returns_paginated_envelope() -> None:
    registry = AsyncMock()
    registry.list_all = AsyncMock(return_value=[_star("star:sirius", "Sirius", -1.46)])
    client = _build_client(registry)

    r = client.get("/catalog/objects")

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["limit"] == 100
    assert body["offset"] == 0
    assert body["objects"][0]["qualified_id"] == "star:sirius"
    assert body["objects"][0]["extras"] == {}


def test_list_objects_propagates_query_params() -> None:
    registry = AsyncMock()
    registry.list_all = AsyncMock(return_value=[])
    client = _build_client(registry)

    r = client.get(
        "/catalog/objects",
        params={"kind": "star", "search": "sir", "max_mag": 1.0,
                "limit": 25, "offset": 10},
    )

    assert r.status_code == 200
    registry.list_all.assert_awaited_once()
    f = registry.list_all.await_args.args[0]
    assert f.kind == "star"
    assert f.search == "sir"
    assert f.max_mag == 1.0
    assert f.limit == 25
    assert f.offset == 10


def test_list_objects_rejects_limit_above_500() -> None:
    registry = AsyncMock()
    client = _build_client(registry)

    r = client.get("/catalog/objects", params={"limit": 501})

    assert r.status_code == 422


def test_list_objects_rejects_negative_offset() -> None:
    registry = AsyncMock()
    client = _build_client(registry)

    r = client.get("/catalog/objects", params={"offset": -1})

    assert r.status_code == 422


def test_get_object_returns_200_when_found() -> None:
    registry = AsyncMock()
    registry.get_by_qualified_id = AsyncMock(
        return_value=_star("star:sirius", "Sirius", -1.46)
    )
    client = _build_client(registry)

    r = client.get("/catalog/objects/star:sirius")

    assert r.status_code == 200
    assert r.json()["name"] == "Sirius"


def test_get_object_returns_404_when_absent() -> None:
    registry = AsyncMock()
    registry.get_by_qualified_id = AsyncMock(return_value=None)
    client = _build_client(registry)

    r = client.get("/catalog/objects/star:missing")

    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_routes.py -v`
Expected: FAIL — `astro_brain.routes.catalog` not found.

- [ ] **Step 3: Add `get_catalog_registry` dependency**

Edit `backend/astro_brain/deps.py` — append at end:

```python
def get_catalog_registry(request: Request) -> Any:
    return request.app.state.catalog_registry
```

- [ ] **Step 4: Implement the router**

Create `backend/astro_brain/routes/catalog.py`:

```python
"""Routes REST du catalogue d'objets célestes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.registry import CatalogRegistry

router = APIRouter(tags=["catalog"], prefix="/catalog")


class CatalogListResponse(BaseModel):
    objects: list[CatalogObject]
    count: int
    limit: int
    offset: int


@router.get("/objects", response_model=CatalogListResponse)
async def list_objects(
    kind: str | None = Query(default=None),
    search: str | None = Query(default=None),
    max_mag: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    registry: CatalogRegistry = Depends(deps.get_catalog_registry),
) -> CatalogListResponse:
    f = CatalogFilter(
        kind=kind, search=search, max_mag=max_mag, limit=limit, offset=offset,
    )
    objects = await registry.list_all(f)
    return CatalogListResponse(
        objects=objects, count=len(objects), limit=limit, offset=offset,
    )


@router.get("/objects/{qualified_id:path}", response_model=CatalogObject)
async def get_object(
    qualified_id: str,
    registry: CatalogRegistry = Depends(deps.get_catalog_registry),
) -> Any:
    obj = await registry.get_by_qualified_id(qualified_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="object not found")
    return obj
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_routes.py -v`
Expected: PASS — 6/6.

- [ ] **Step 6: Commit**

```bash
git add backend/astro_brain/routes/catalog.py backend/astro_brain/deps.py backend/tests/test_catalog_routes.py
git commit -m "feat(backend): /catalog/objects router (list + get with kind/search/max_mag)"
```

---

## Task 7: Wire catalog into `app.py`

**Files:**
- Modify: `backend/astro_brain/app.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_app.py` (or create a new `tests/test_catalog_wiring.py` if `test_app.py` is unfit):

```python
def test_build_app_exposes_catalog_registry(tmp_path) -> None:
    from astro_brain.app import build_app

    app = build_app(use_hardware=False, db_path_override=tmp_path / "state.db")
    with TestClient(app):
        assert hasattr(app.state, "catalog_registry")
        assert "star" in app.state.catalog_registry._providers


def test_catalog_objects_route_is_registered(tmp_path) -> None:
    from astro_brain.app import build_app

    app = build_app(use_hardware=False, db_path_override=tmp_path / "state.db")
    with TestClient(app) as client:
        r = client.get("/catalog/objects")
        assert r.status_code == 200
        body = r.json()
        assert "objects" in body
        assert "count" in body
```

(Si `test_app.py` n'a pas déjà l'import `TestClient`, ajouter `from fastapi.testclient import TestClient` en haut du fichier.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_app.py::test_build_app_exposes_catalog_registry tests/test_app.py::test_catalog_objects_route_is_registered -v`
Expected: FAIL — `app.state.catalog_registry` doesn't exist; `/catalog/objects` returns 404.

- [ ] **Step 3: Wire the registry, seed runner, and router**

Edit `backend/astro_brain/app.py`. Add imports near the other catalog/services imports:

```python
from importlib.resources import as_file, files

from astro_brain.routes.catalog import router as catalog_router
from astro_brain.services.catalog.providers import SqliteCatalogProvider
from astro_brain.services.catalog.registry import CatalogRegistry
from astro_brain.services.catalog.seed_runner import apply_seeds
```

Inside `lifespan`, after `await run_migrations(db_conn)` and before the calibration_service block, add:

```python
        with as_file(files("astro_brain.data")) as data_dir:
            await apply_seeds(db_conn, data_dir)

        _app.state.catalog_registry = CatalogRegistry({
            "star": SqliteCatalogProvider(db_conn, kind="star"),
        })
```

After the existing `app.include_router(alignment_router)` line, add:

```python
    app.include_router(catalog_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_app.py -v`
Expected: PASS for the two new tests; existing tests still green.

- [ ] **Step 5: Run the full backend suite to check no regression**

Run: `cd backend && uv run pytest -q`
Expected: PASS — full suite green.

- [ ] **Step 6: Commit**

```bash
git add backend/astro_brain/app.py backend/tests/test_app.py
git commit -m "feat(backend): wire catalog registry + seed_runner + /catalog routes in app lifespan"
```

---

## Task 8: Seed generation tool `tools/seed_stars.py` (with offline tests)

**Files:**
- Create: `backend/tools/seed_stars.py`
- Create: `backend/tests/test_seed_stars_tool.py`
- Create: `backend/tests/fixtures/iau_csn_excerpt.txt` (fixture)

**Note** : ce script tournera sur la workstation pour régénérer `seed_stars.sql`. On le teste **offline** avec un extrait CSV en fixture (pas d'appel réseau dans la suite pytest). Le pull réel se fait à l'étape 9.

- [ ] **Step 1: Create the IAU CSN fixture**

Create `backend/tests/fixtures/iau_csn_excerpt.txt` (extrait minimal du format IAU CSN, voir https://www.iau.org/static/public/themes/naming_stars/IAU-CSN.txt — colonnes fixes séparées par espaces) :

```
# IAU Catalog of Star Names (CSN) — fixture pour tests offline
# Format approximatif: Name | Designation | ID | Bayer | Const | WDS | Vmag | RA(deg) | Dec(deg) | Date | Notes
#Name      |Designation|ID  |Bayer |Const|WDS_J         |Vmag |RA(J2000)|Dec(J2000)|Date     |Notes
Sirius     |alf CMa A  |HR2491|alf  |CMa  |J06451-1643AP |-1.46|101.28715|-16.71612 |2016-06-30|approved
Vega       |alf Lyr    |HR7001|alf  |Lyr  |              | 0.03|279.23473| 38.78369 |2016-06-30|approved
Polaris    |alf UMi Aa |HR424 |alf  |UMi  |J02319+8915Aa |1.98 | 37.95456| 89.26411 |2016-06-30|approved
Betelgeuse |alf Ori    |HR2061|alf  |Ori  |              |0.42 | 88.79294|  7.40706 |2016-06-30|approved
Faintstar  |xxx Xxx    |HR9999|xxx  |Xxx  |              | 4.50|123.4    | 45.6     |2016-06-30|approved
```

(Le format réel a colonnes fixes par caractère — l'implémentation doit accepter le format documenté CSN. Cette fixture mime ce format.)

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_seed_stars_tool.py`:

```python
"""Tests offline du dev tool tools/seed_stars.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from seed_stars import build_sql, parse_csn  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "iau_csn_excerpt.txt"


def test_parse_csn_extracts_named_stars() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))

    by_name = {r.name: r for r in rows}
    assert "Sirius" in by_name
    assert "Vega" in by_name
    assert by_name["Sirius"].mag == pytest.approx(-1.46)
    assert by_name["Sirius"].ra_deg == pytest.approx(101.28715)
    assert by_name["Sirius"].dec_deg == pytest.approx(-16.71612)
    assert by_name["Sirius"].constellation == "CMa"


def test_parse_csn_skips_comments_and_blank() -> None:
    text = "# header\n\n# another\n"
    assert parse_csn(text) == []


def test_build_sql_filters_by_max_mag() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))

    sql = build_sql(rows, max_mag=3.0)

    # Faintstar (mag 4.5) excluded; Sirius/Vega/Polaris/Betelgeuse included
    assert "Sirius" in sql
    assert "Vega" in sql
    assert "Polaris" in sql
    assert "Betelgeuse" in sql
    assert "Faintstar" not in sql


def test_build_sql_uses_insert_or_replace() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql = build_sql(rows, max_mag=3.0)
    assert "INSERT OR REPLACE INTO catalog_objects" in sql


def test_build_sql_qualifies_id_with_kind_prefix() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql = build_sql(rows, max_mag=3.0)
    assert "'star:sirius'" in sql.lower()


def test_build_sql_is_deterministic() -> None:
    rows = parse_csn(FIXTURE.read_text(encoding="utf-8"))
    sql1 = build_sql(rows, max_mag=3.0)
    sql2 = build_sql(rows, max_mag=3.0)
    assert sql1 == sql2


def test_build_sql_escapes_single_quotes() -> None:
    from seed_stars import StarRow

    row = StarRow(
        slug="weird", name="O'Brian Star", designation="alf X",
        constellation="X", ra_deg=0.0, dec_deg=0.0, mag=1.0,
    )
    sql = build_sql([row], max_mag=3.0)
    assert "O''Brian Star" in sql
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_seed_stars_tool.py -v`
Expected: FAIL — `seed_stars` module not found.

- [ ] **Step 4: Implement `tools/seed_stars.py`**

Create `backend/tools/seed_stars.py`:

```python
"""Generate `astro_brain/data/seed_stars.sql` from the IAU CSN catalogue.

Usage:
    cd backend
    uv run python tools/seed_stars.py --output astro_brain/data/seed_stars.sql

By default pulls https://www.iau.org/static/public/themes/naming_stars/IAU-CSN.txt
and filters to stars with V mag ≤ 3.0. Pass --input <path> to use a local
fixture instead of the network. Output `.sql` is committed to the repo;
re-running with the same source produces a byte-identical file.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CSN_URL = "https://www.iau.org/static/public/themes/naming_stars/IAU-CSN.txt"
DEFAULT_MAX_MAG = 3.0


@dataclass(frozen=True)
class StarRow:
    slug: str
    name: str
    designation: str
    constellation: str
    ra_deg: float
    dec_deg: float
    mag: float


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return s


def _parse_float(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def parse_csn(text: str) -> list[StarRow]:
    """Parse the IAU CSN text format into ``StarRow`` records.

    The file is pipe-separated in this codebase's fixtures, with comment lines
    starting with ``#``. Real CSN data is fixed-width — adjust here if the
    upstream format ever differs from the fixture used in tests.
    """
    rows: list[StarRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 9:
            continue
        name = parts[0]
        designation = parts[1]
        constellation = parts[4]
        mag = _parse_float(parts[6])
        ra = _parse_float(parts[7])
        dec = _parse_float(parts[8])
        if mag is None or ra is None or dec is None or not name:
            continue
        rows.append(
            StarRow(
                slug=_slugify(name),
                name=name,
                designation=designation,
                constellation=constellation,
                ra_deg=ra,
                dec_deg=dec,
                mag=mag,
            )
        )
    return rows


def _sql_quote(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def build_sql(rows: list[StarRow], *, max_mag: float) -> str:
    """Return a deterministic `.sql` body containing INSERT OR REPLACE rows."""
    keep = sorted(
        (r for r in rows if r.mag <= max_mag and r.slug),
        key=lambda r: r.slug,
    )
    lines: list[str] = [
        "-- Generated by tools/seed_stars.py — DO NOT EDIT BY HAND.",
        f"-- Source: {CSN_URL}",
        f"-- Filter: V mag <= {max_mag}",
        "",
    ]
    for r in keep:
        qid = f"star:{r.slug}"
        lines.append(
            "INSERT OR REPLACE INTO catalog_objects "
            "(id, kind, name, designation, ra_deg, dec_deg, mag, constellation) "
            f"VALUES ({_sql_quote(qid)}, 'star', {_sql_quote(r.name)}, "
            f"{_sql_quote(r.designation)}, {r.ra_deg:.5f}, {r.dec_deg:.5f}, "
            f"{r.mag:.2f}, {_sql_quote(r.constellation)});"
        )
    return "\n".join(lines) + "\n"


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:  # nosec - dev tool
        return resp.read().decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None,
                        help="local CSV path (offline mode); defaults to fetching IAU URL")
    parser.add_argument("--output", type=Path, required=True,
                        help="output .sql path (e.g. astro_brain/data/seed_stars.sql)")
    parser.add_argument("--max-mag", type=float, default=DEFAULT_MAX_MAG,
                        help=f"cap visible magnitude (default {DEFAULT_MAX_MAG})")
    ns = parser.parse_args(argv)

    text = ns.input.read_text(encoding="utf-8") if ns.input else _fetch(CSN_URL)
    rows = parse_csn(text)
    sql = build_sql(rows, max_mag=ns.max_mag)
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(sql, encoding="utf-8")
    print(f"wrote {len(sql.splitlines())} lines → {ns.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_seed_stars_tool.py -v`
Expected: PASS — 7/7.

- [ ] **Step 6: Commit**

```bash
git add backend/tools/seed_stars.py backend/tests/test_seed_stars_tool.py backend/tests/fixtures/iau_csn_excerpt.txt
git commit -m "feat(backend): tools/seed_stars.py (IAU CSN → seed_stars.sql) + offline tests"
```

---

## Task 9: Generate the real `seed_stars.sql` from IAU CSN

**Files:**
- Create: `backend/astro_brain/data/seed_stars.sql` (committed, generated)

**Note** : étape de **génération de données réelles**. Pas de tests TDD ici — la sortie sert d'input à Task 10.

- [ ] **Step 1: Pull and generate**

Run: `cd backend && uv run python tools/seed_stars.py --output astro_brain/data/seed_stars.sql`

Expected stderr: `wrote N lines → astro_brain/data/seed_stars.sql` avec N entre ~50 et ~200 (selon le filtre cap mag 3.0).

- [ ] **Step 2: Sanity-check the output**

Run: `head -20 backend/astro_brain/data/seed_stars.sql`
Expected: header `-- Generated by tools/seed_stars.py` + plusieurs `INSERT OR REPLACE INTO catalog_objects ...` mentionnant `'star:sirius'`, `'star:vega'`, `'star:polaris'`.

Run: `grep -c '^INSERT OR REPLACE' backend/astro_brain/data/seed_stars.sql`
Expected: ≥ 50 lignes.

- [ ] **Step 3: If the IAU upstream parsing fails**

Si la sortie est vide (≤ 5 lignes) parce que le format réel CSN diffère de la fixture, ajuster `parse_csn` pour le format **fixed-width réel** (colonnes 0-17 = name, etc., voir l'en-tête de l'IAU-CSN.txt téléchargé). Re-tester `tests/test_seed_stars_tool.py` (la fixture est sous notre contrôle, donc reste verte ; ajouter une fixture supplémentaire si besoin pour couvrir le format fixed-width réel) puis re-générer.

- [ ] **Step 4: Commit the generated seed**

```bash
git add backend/astro_brain/data/seed_stars.sql
git commit -m "feat(backend): seed_stars.sql committed (~N IAU named stars cap mag 3.0)"
```

(Remplacer `N` par le nombre réel de lignes INSERT.)

---

## Task 10: Smoke test — real seed loads ≥ 50 stars including key entries

**Files:**
- Create: `backend/tests/test_catalog_seed_stars_smoke.py`

- [ ] **Step 1: Write the smoke test**

Create `backend/tests/test_catalog_seed_stars_smoke.py`:

```python
"""Smoke test: the real committed seed_stars.sql loads correctly."""
from __future__ import annotations

from collections.abc import AsyncIterator
from importlib.resources import as_file, files

import aiosqlite
import pytest

from astro_brain.repository.state_db import run_migrations
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import SqliteCatalogProvider
from astro_brain.services.catalog.seed_runner import apply_seeds


@pytest.fixture
async def db_with_seeds() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    try:
        await run_migrations(conn)
        with as_file(files("astro_brain.data")) as data_dir:
            await apply_seeds(conn, data_dir)
        yield conn
    finally:
        await conn.close()


async def test_seed_stars_loads_at_least_50_entries(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    cursor = await db_with_seeds.execute(
        "SELECT COUNT(*) FROM catalog_objects WHERE kind = 'star'"
    )
    row = await cursor.fetchone()
    await cursor.close()
    assert row is not None
    assert row[0] >= 50


async def test_seed_stars_contains_iconic_entries(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    provider = SqliteCatalogProvider(db_with_seeds, kind="star")

    sirius = await provider.get_object("sirius")
    vega = await provider.get_object("vega")
    polaris = await provider.get_object("polaris")

    assert sirius is not None and sirius.name == "Sirius"
    assert vega is not None and vega.name == "Vega"
    assert polaris is not None and polaris.name == "Polaris"


async def test_seed_stars_has_valid_coordinates(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    cursor = await db_with_seeds.execute(
        "SELECT id, ra_deg, dec_deg FROM catalog_objects WHERE kind = 'star'"
    )
    rows = await cursor.fetchall()
    await cursor.close()
    for qid, ra, dec in rows:
        assert 0.0 <= ra < 360.0, f"{qid}: ra={ra}"
        assert -90.0 <= dec <= 90.0, f"{qid}: dec={dec}"


async def test_seed_stars_max_mag_filter_works(
    db_with_seeds: aiosqlite.Connection,
) -> None:
    provider = SqliteCatalogProvider(db_with_seeds, kind="star")

    bright = await provider.list_objects(CatalogFilter(max_mag=2.0, limit=500))

    assert len(bright) >= 10
    for obj in bright:
        assert obj.mag is not None and obj.mag <= 2.0
```

- [ ] **Step 2: Run the smoke test**

Run: `cd backend && uv run pytest tests/test_catalog_seed_stars_smoke.py -v`
Expected: PASS — 4/4.

- [ ] **Step 3: Run the full suite to confirm no regression**

Run: `cd backend && uv run pytest -q`
Expected: PASS — full backend suite green (incl. les 89 tests existants + les nouveaux).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_catalog_seed_stars_smoke.py
git commit -m "test(backend): smoke test catalog seed loads real IAU stars (Sirius/Vega/Polaris)"
```

---

## Task 11: Update roadmap + journal

**Files:**
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/journal.md`

- [ ] **Step 1: Update roadmap**

Edit `docs/project/roadmap.md` Macro 3 #4 line — passer la première puce de 📦 à 🚧 ou ✅ selon ce qui sort de la session :

```markdown
- 🚧 Catalogue minimal backend : tranche A (stars étendues IAU CSN cap mag 3) livrée 2026-05-10 — tranches Messier + planètes à suivre
```

- [ ] **Step 2: Update journal**

Append to `docs/project/journal.md` un bloc session :

```markdown
## Session 23 — 2026-05-10 — Catalogue backend tranche A (stars)

- Migration `_003_catalog_objects` (table unifiée `catalog_objects`, 3 indexes).
- Architecture catalogue : `CatalogProvider` Protocol + `SqliteCatalogProvider`, dispatch via `CatalogRegistry`, seed_runner idempotent au boot.
- Seed pipeline : `tools/seed_stars.py` (IAU CSN → `.sql`), `astro_brain/data/seed_stars.sql` committé.
- Endpoint `GET /catalog/objects` (kind/search/max_mag/limit/offset) + `GET /catalog/objects/{qualified_id}`.
- Tests : N nouveaux (modèles, provider, registry, seed_runner, routes, tool dev, smoke).
- Tranche A+1 (refactor wizard pour consommer le provider) reportée. `_alignment_stars.json` reste en place tant que.
```

- [ ] **Step 3: Commit**

```bash
git add docs/project/roadmap.md docs/project/journal.md
git commit -m "docs: session 23 + roadmap Macro 3 #4 tranche A (stars catalogue)"
```

---

## Self-review checklist (post-plan)

Before handing off to execution, verify:

1. **Spec coverage** — chaque section In-scope du spec a au moins une tâche :
   - Table sqlite + indexes → Task 1
   - `CatalogProvider` + `SqliteCatalogProvider` → Task 3
   - `CatalogRegistry` → Task 4
   - Seed runner idempotent → Task 5
   - Tool dev `seed_stars.py` → Task 8
   - Endpoint `GET /catalog/objects` + `/{qid}` → Task 6
   - Tests d'idempotence, provider, registry, routes, smoke réel → Tasks 5/3/4/6/10
   - Wire dans app → Task 7
   - Génération du seed réel → Task 9

2. **Out-of-scope respecté** — aucun task ne touche `_alignment_catalog`, ne calcule `visible_now`, ne charge Messier/planètes, ne touche l'app Flutter. ✅

3. **Type/nom consistency** — `CatalogObject.qualified_id`, `CatalogFilter`, `SqliteCatalogProvider(db, kind=...)`, `CatalogRegistry({"star": ...})`, `apply_seeds(db, data_dir)` cohérents partout. ✅

4. **Erreurs / placeholders** — pas de TBD, code complet dans chaque step, commandes pytest exactes. ✅

5. **Risque** — Task 9 dépend du format réel IAU CSN ; Task 8 inclut un fallback explicite (Step 3 de Task 9) si le format diffère de la fixture.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-catalog-backend-stars.md`. Two execution options:

1. **Subagent-Driven (recommended)** — Je dispatche un subagent par tâche, je review entre tâches, itération rapide.
2. **Inline Execution** — Exécution dans cette session avec checkpoints.

Which approach?
