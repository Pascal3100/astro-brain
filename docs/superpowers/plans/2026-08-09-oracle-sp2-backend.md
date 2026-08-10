# Oracle SP2 — Consommateur backend (Pi lit `reference.sqlite`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire du backend Pi un consommateur de `reference.sqlite` v2 — il télécharge l'artefact publié par SP1, l'interroge hors-ligne (catalogue complet toutes familles), et pointe n'importe quel objet par son `id`.

**Architecture:** Un fichier `reference.sqlite` séparé de `state.db`, ouvert par une 2ᵉ connexion aiosqlite **lecture seule** dont le handle est swappable sous verrou après une sync (fetch conditionnel sha256, online-first, non bloquant). Deux providers lisent ce handle — `FixedObjectProvider` (dso/star → `fixed_object`) et `EphemerisProvider` (comet/planet/moon/sun → `ephemeris`, interpolé à l'instant courant). Une façade `ReferenceCatalog` route les requêtes et le `TargetResolver` sert le GoTo par `id`.

**Tech Stack:** FastAPI, aiosqlite (connexion RO `mode=ro`), httpx (déjà dépendance), pytest/pytest-asyncio. Python 3.13, `uv`.

## Global Constraints

- **Python** : respecter les PEPs (8, 257, 484/604). `from __future__ import annotations` en tête de chaque module. Types complets sur les signatures publiques.
- **Schéma consommé** : v2 uniquement. Constante `SUPPORTED_SCHEMA_VERSION = 2`. Refuser (garder le cache) tout artefact `meta.schema_version > 2`. Source de vérité du schéma : `oracle/schema.sql` — ne jamais importer depuis `oracle/`.
- **Contrat manifest** (SP1) : `manifest.json` = `{ schema_version, generated_at, sqlite_url, sqlite_sha256, window_start, window_end }`. Télécharger le SQLite seulement quand `sqlite_sha256` change.
- **RA/Dec** = apparent of-date (JNow) dans la base ; le backend ne fait que LST→alt/az via `astro_brain.services._ephemeris.sky_az_alt_from_ra_dec` — **aucune nouvelle trigonométrie**.
- **URL manifest par défaut** : `https://github.com/Pascal3100/astro-brain/releases/download/almanac-latest/manifest.json`, surchargeable par l'env `ASTRO_BRAIN_REFERENCE_MANIFEST_URL`.
- **Chemin cache** : `<state_dir>/reference.sqlite`, à côté de `state.db` (même répertoire que `state_db.db_path()`), fichier distinct — **jamais d'`ATTACH`** entre les deux bases.
- **`reference_ready = false`** (cache absent/non supporté) : dégradation propre — `GET /catalog/objects` renvoie **200 liste vide**, `POST /goto` renvoie **409 `reference_unavailable`**.
- **Vocabulaire `kind`** = `comet | planet | moon | sun | dso | star`. Messier = sous-ensemble `dso` où la colonne `messier` est non-nulle (exposé via le paramètre `messier=true`).
- **Le train (`docs/project/roadmap.md`)** n'a pas de macro à bouger (Oracle est un fil transverse) ; **mettre à jour le journal `docs/project/journal.md`** pendant la session d'implémentation.
- **Suite verte à chaque frontière de tâche.** Tout le nouveau code (Tâches 1→13) est **additif** — l'ancienne source (`catalog_objects` + `SqliteCatalogProvider` + `apply_seeds`) reste en place et testée jusqu'à la **Tâche 14 (bascule)**, seul point où l'ancien stack et les tests obsolètes sont supprimés.
- **Commandes** : depuis `backend/`, `uv run pytest <path> -v` pour un test ciblé, `uv run pytest` pour la suite. Toute commande bash modifiant l'état (commit inclus) requiert validation utilisateur (règle projet).

### Décisions tranchées (questions ouvertes du design)

1. **Surfacage de l'état référence** : nouvel endpoint dédié `GET /reference/status` (ne pas polluer `GET /about`, qui porte l'identité backend/réseau/uptime).
2. **Coût liste** : l'interpolation linéaire de ~953 comètes par requête est arithmétiquement triviale ; on conserve `limit` par défaut 100 et l'index `idx_ephem_time` existant. Pas d'index supplémentaire. À re-mesurer sur Pi 3 B+ si une lenteur apparaît (noté, non bloquant).
3. **Fixture de test** : helper `tests/reference_fixtures.py` qui construit un **petit `reference.sqlite` v2 en fichier temp** via SQL brut (pas d'import `oracle/`, pas de binaire commité).
4. **Éphémère hors-fenêtre** (raffinement de la formulation lâche du design) : pour `GET /catalog/objects`, un objet éphémère non plaçable à `now` (cache périmé) est **omis** de la liste (réponse honnête : « on ne peut pas le situer maintenant »). Pour `POST /goto` d'un `id` éphémère précis, `get_object` renvoie l'objet **marqué `ephemeris_stale=True`** (coords = échantillon-frontière le plus proche) afin que la route réponde **409 `ephemeris_stale`** avec une cause claire.
5. **Ordre des gardes GoTo** : la vérif `reference_unavailable` (409) précède `unknown_id` (404) — impossible de classer un id inconnu sans base chargée. Ordre effectif : `409 reference_unavailable` → `404 unknown_id` → `409 ephemeris_stale` → `409 not_aligned` → `409 goto_in_progress` → `409 solar_ack_required`.

---

## File Structure

**Créés :**
- `backend/astro_brain/repository/reference_db.py` — chemin/URL, connexion RO swappable, `meta`, sha256 local.
- `backend/astro_brain/services/catalog/interpolation.py` — interpolation linéaire pure + wrap RA + parse UTC.
- `backend/astro_brain/services/catalog/reference_catalog.py` — façade `ReferenceCatalog` (routing + merge + `get_by_qualified_id`).
- `backend/astro_brain/services/catalog/resolver.py` — `TargetResolver` (id → cible GoTo).
- `backend/astro_brain/services/reference/__init__.py` + `sync.py` — `ReferenceSync` (fetch/verify/swap).
- `backend/astro_brain/routes/reference.py` — `GET /reference/status`, `POST /reference/sync`.
- `backend/astro_brain/repository/migrations/_004_drop_catalog_objects.py` — DROP `catalog_objects`.
- `backend/tests/reference_fixtures.py` — builder du `reference.sqlite` v2 de test.

**Modifiés :**
- `backend/astro_brain/services/catalog/models.py` — kind v2, champs optionnels, `messier_only`.
- `backend/astro_brain/services/catalog/providers.py` — `FixedObjectProvider`, `EphemerisProvider` (ajout ; `SqliteCatalogProvider` supprimé en T14).
- `backend/astro_brain/services/catalog/visibility.py` — gérer `ephemeris_stale`.
- `backend/astro_brain/routes/catalog.py` — paramètre `messier`.
- `backend/astro_brain/routes/goto.py` — contrat id-only + gardes.
- `backend/astro_brain/deps.py` — resolvers `get_reference_db`, `get_reference_sync`, `get_resolver`.
- `backend/astro_brain/app.py` — câblage stack référence + tâche sync (T14).

**Supprimés (T14) :** `data/seed_stars.sql`, `tools/seed_stars.py`, `services/catalog/seed_runner.py`, `SqliteCatalogProvider` + `CatalogRegistry` (dans providers.py/registry.py), tests `test_catalog_seed_runner.py`, `test_catalog_seed_stars_smoke.py`, `test_seed_stars_tool.py`, `test_catalog_sqlite_provider.py`, `test_catalog_registry.py`.

---

## Task 1: Interpolation pure (RA/Dec à un instant)

**Files:**
- Create: `backend/astro_brain/services/catalog/interpolation.py`
- Test: `backend/tests/test_catalog_interpolation.py`

**Interfaces:**
- Produces:
  - `def parse_utc(s: str) -> datetime` — parse ISO-8601 (accepte suffixe `Z`), force tz UTC si naïf.
  - `def lerp(a: float, b: float, frac: float) -> float`
  - `def lerp_angle_deg(a: float, b: float, frac: float) -> float` — interpolation sur le plus court arc, résultat dans `[0, 360)`.
  - `def interpolate_radec(before: tuple[datetime, float, float], after: tuple[datetime, float, float], t: datetime) -> tuple[float, float]` — `(sample_utc, ra_deg, dec_deg)` → `(ra_deg, dec_deg)` à `t`. `frac` clampé `[0,1]`; si `before == after` (span nul) renvoie les coords de `before`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_catalog_interpolation.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from astro_brain.services.catalog.interpolation import (
    interpolate_radec,
    lerp_angle_deg,
    parse_utc,
)


def test_parse_utc_accepts_z_suffix() -> None:
    t = parse_utc("2026-08-09T00:00:00Z")
    assert t == datetime(2026, 8, 9, 0, 0, 0, tzinfo=UTC)


def test_parse_utc_forces_utc_when_naive() -> None:
    assert parse_utc("2026-08-09T00:00:00").tzinfo == UTC


def test_lerp_angle_wraps_shortest_arc_through_zero() -> None:
    # 359° -> 1° à mi-chemin doit passer par 0°, pas par 180°
    assert lerp_angle_deg(359.0, 1.0, 0.5) == pytest.approx(0.0, abs=1e-9)


def test_interpolate_radec_midpoint() -> None:
    before = (datetime(2026, 8, 9, 0, 0, tzinfo=UTC), 100.0, 10.0)
    after = (datetime(2026, 8, 10, 0, 0, tzinfo=UTC), 102.0, 12.0)
    t = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    ra, dec = interpolate_radec(before, after, t)
    assert ra == pytest.approx(101.0)
    assert dec == pytest.approx(11.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_interpolation.py -v`
Expected: FAIL (`ModuleNotFoundError: astro_brain.services.catalog.interpolation`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/astro_brain/services/catalog/interpolation.py
"""Interpolation linéaire pure des éphémères (RA/Dec à un instant donné).

Aucune I/O. Les échantillons sont journaliers ; on interpole linéairement
entre les deux qui encadrent l'instant, en prenant le plus court arc pour le
RA (gère 359°→1° sans téléporter). Partagé par le provider éphémère et le
resolver GoTo.
"""
from __future__ import annotations

from datetime import UTC, datetime


def parse_utc(s: str) -> datetime:
    """Parse un ISO-8601 (suffixe ``Z`` accepté) en datetime tz-aware UTC."""
    text = s.replace("Z", "+00:00") if s.endswith("Z") else s
    t = datetime.fromisoformat(text)
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * frac


def lerp_angle_deg(a: float, b: float, frac: float) -> float:
    """Interpole un angle (deg) sur le plus court arc ; résultat dans [0, 360)."""
    diff = ((b - a + 180.0) % 360.0) - 180.0
    return (a + diff * frac) % 360.0


def interpolate_radec(
    before: tuple[datetime, float, float],
    after: tuple[datetime, float, float],
    t: datetime,
) -> tuple[float, float]:
    """Interpole (ra, dec) à ``t`` entre deux échantillons ``(utc, ra, dec)``."""
    t0, ra0, dec0 = before
    t1, ra1, dec1 = after
    span = (t1 - t0).total_seconds()
    if span == 0:
        return ra0 % 360.0, dec0
    frac = (t - t0).total_seconds() / span
    frac = max(0.0, min(1.0, frac))
    return lerp_angle_deg(ra0, ra1, frac), lerp(dec0, dec1, frac)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_interpolation.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/interpolation.py backend/tests/test_catalog_interpolation.py
git commit -m "feat(oracle): interpolation linéaire pure des éphémères (SP2 T1)"
```

---

## Task 2: Handle de la base référence (`ReferenceDb`)

**Files:**
- Create: `backend/astro_brain/repository/reference_db.py`
- Test: `backend/tests/test_reference_db.py`

**Interfaces:**
- Consumes: `astro_brain.repository.state_db.STATE_DIR_ENV`, `STATE_DIR_DEFAULT`.
- Produces:
  - `REFERENCE_FILENAME = "reference.sqlite"`, `MANIFEST_URL_ENV = "ASTRO_BRAIN_REFERENCE_MANIFEST_URL"`, `DEFAULT_MANIFEST_URL: str`, `SUPPORTED_SCHEMA_VERSION = 2`.
  - `def reference_path() -> Path` — `<state_dir>/reference.sqlite` (crée le dir parent).
  - `def manifest_url() -> str` — env ou défaut.
  - `def local_sha256(path: Path) -> str | None` — hex sha256 du fichier, `None` si absent.
  - `@dataclass(frozen=True) class ReferenceMeta: schema_version: int; generated_at: str; window_start: str; window_end: str`.
  - `class ReferenceDb`: `__init__(self, path: Path)`; `path: Path` (prop) ; `ready: bool` (prop) ; `async open(self) -> None` ; `async reopen(self) -> None` ; `def current(self) -> aiosqlite.Connection | None` ; `async meta(self) -> ReferenceMeta | None` ; `async close(self) -> None`. `open`/`reopen` : ouvrent une connexion RO (`file:{path}?mode=ro&immutable=1`, `uri=True`) seulement si le fichier existe **et** `meta.schema_version <= SUPPORTED_SCHEMA_VERSION` ; sinon `current()` reste `None`. `reopen` ferme l'ancienne sous `asyncio.Lock`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from astro_brain.repository.reference_db import (
    SUPPORTED_SCHEMA_VERSION,
    ReferenceDb,
    local_sha256,
)


def _write_min_v2(path: Path, schema_version: int = 2) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE meta (schema_version INTEGER NOT NULL, generated_at TEXT,"
        " mpc_epoch TEXT, window_start TEXT NOT NULL, window_end TEXT NOT NULL,"
        " skyfield_kernel TEXT);"
    )
    con.execute(
        "INSERT INTO meta (schema_version, generated_at, window_start, window_end)"
        " VALUES (?, ?, ?, ?)",
        (schema_version, "2026-08-09T00:00:00Z", "2026-08-09", "2026-10-08"),
    )
    con.commit()
    con.close()


async def test_open_absent_file_is_not_ready(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    assert ref.ready is False
    assert ref.current() is None


async def test_open_v2_is_ready_and_reads_meta(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    _write_min_v2(p, schema_version=2)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is True
    meta = await ref.meta()
    assert meta is not None
    assert meta.schema_version == SUPPORTED_SCHEMA_VERSION
    assert meta.window_end == "2026-10-08"
    await ref.close()


async def test_open_future_schema_is_rejected(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    _write_min_v2(p, schema_version=3)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is False


def test_local_sha256_absent_is_none(tmp_path: Path) -> None:
    assert local_sha256(tmp_path / "nope.sqlite") is None
```

Note : ajouter `pytestmark = pytest.mark.asyncio` si la config n'active pas déjà `asyncio_mode=auto` — vérifier `pyproject.toml`/`pytest.ini`. (Les tests async existants du repo n'ont pas de décorateur → mode auto probable ; sinon décorer.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reference_db.py -v`
Expected: FAIL (`ModuleNotFoundError: astro_brain.repository.reference_db`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/astro_brain/repository/reference_db.py
"""Connexion lecture seule à `reference.sqlite` (artefact SP1, jetable).

Fichier distinct de `state.db` : RO, remplacé en bloc par la sync. Le handle
courant est swappable sous verrou (une sync réouvre sans perturber les
requêtes en cours). Le backend refuse d'adopter un schema_version > 2.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from astro_brain.repository.state_db import STATE_DIR_DEFAULT, STATE_DIR_ENV

REFERENCE_FILENAME = "reference.sqlite"
MANIFEST_URL_ENV = "ASTRO_BRAIN_REFERENCE_MANIFEST_URL"
DEFAULT_MANIFEST_URL = (
    "https://github.com/Pascal3100/astro-brain/releases/download/"
    "almanac-latest/manifest.json"
)
SUPPORTED_SCHEMA_VERSION = 2


def reference_path() -> Path:
    state_dir = Path(os.environ.get(STATE_DIR_ENV, STATE_DIR_DEFAULT))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / REFERENCE_FILENAME


def manifest_url() -> str:
    return os.environ.get(MANIFEST_URL_ENV, DEFAULT_MANIFEST_URL)


def local_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ReferenceMeta:
    schema_version: int
    generated_at: str
    window_start: str
    window_end: str


class ReferenceDb:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def ready(self) -> bool:
        return self._conn is not None

    def current(self) -> aiosqlite.Connection | None:
        return self._conn

    async def _open_supported(self) -> aiosqlite.Connection | None:
        if not self._path.exists():
            return None
        uri = f"file:{self._path}?mode=ro&immutable=1"
        conn = await aiosqlite.connect(uri, uri=True)
        try:
            cursor = await conn.execute("SELECT schema_version FROM meta LIMIT 1")
            row = await cursor.fetchone()
            await cursor.close()
        except Exception:
            await conn.close()
            return None
        if row is None or int(row[0]) > SUPPORTED_SCHEMA_VERSION:
            await conn.close()
            return None
        return conn

    async def open(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
            self._conn = await self._open_supported()

    async def reopen(self) -> None:
        await self.open()

    async def meta(self) -> ReferenceMeta | None:
        conn = self._conn
        if conn is None:
            return None
        cursor = await conn.execute(
            "SELECT schema_version, generated_at, window_start, window_end"
            " FROM meta LIMIT 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return ReferenceMeta(
            schema_version=int(row[0]),
            generated_at=row[1],
            window_start=row[2],
            window_end=row[3],
        )

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reference_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/repository/reference_db.py backend/tests/test_reference_db.py
git commit -m "feat(oracle): connexion RO swappable reference.sqlite + garde schéma (SP2 T2)"
```

---

## Task 3: Fixture de test `reference.sqlite` v2

**Files:**
- Create: `backend/tests/reference_fixtures.py`
- Test: `backend/tests/test_reference_fixtures.py`

**Interfaces:**
- Consumes: `ReferenceDb` (T2).
- Produces:
  - `FIX_NOW: datetime` — instant de test dans la fenêtre (`2026-08-09T12:00:00Z`).
  - `def build_reference_v2(path: Path) -> None` — écrit un `reference.sqlite` v2 complet via `sqlite3` : `meta` (window `2026-08-08`→`2026-10-07`), `objects` (1 par famille), `fixed_object` (Vega=`star:HIP91262`, M42=`NGC1976`), `ephemeris` (échantillons journaliers `2026-08-08`→`2026-08-11` pour `planet:mars`, `moon`, `sun`, `comet:CK...`), avec RA/Dec choisis pour rendre l'interpolation vérifiable et `illumination` non-nulle pour `moon`.

Le contenu exact des lignes est fixé ci-dessous ; les tâches suivantes s'appuient sur ces valeurs (Mars à `FIX_NOW` = RA 150.5 / Dec 11.5 par interpolation ; Vega au-dessus de l'horizon depuis Paris ; M42 `messier='M42'`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_fixtures.py
from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from tests.reference_fixtures import build_reference_v2


async def test_fixture_builds_supported_v2(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    assert ref.ready is True
    meta = await ref.meta()
    assert meta is not None and meta.schema_version == 2
    await ref.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reference_fixtures.py -v`
Expected: FAIL (`ModuleNotFoundError: tests.reference_fixtures`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/tests/reference_fixtures.py
"""Builder d'un petit `reference.sqlite` v2 pour les tests (SQL brut, temp).

Ne dépend pas de `oracle/`. Valeurs choisies pour rendre l'interpolation et la
visibilité déterministes (voir SP2 plan, Task 3).
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

FIX_NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

_SCHEMA = """
CREATE TABLE meta (schema_version INTEGER NOT NULL, generated_at TEXT NOT NULL,
  mpc_epoch TEXT, window_start TEXT NOT NULL, window_end TEXT NOT NULL,
  skyfield_kernel TEXT);
CREATE TABLE objects (id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT,
  designation TEXT);
CREATE TABLE fixed_object (object_id TEXT PRIMARY KEY REFERENCES objects(id),
  ra_deg REAL NOT NULL, dec_deg REAL NOT NULL, apparent_mag REAL,
  object_type TEXT, size_arcmin REAL, constellation TEXT, messier TEXT,
  ngc_ic TEXT);
CREATE TABLE ephemeris (object_id TEXT NOT NULL REFERENCES objects(id),
  sample_utc TEXT NOT NULL, ra_deg REAL NOT NULL, dec_deg REAL NOT NULL,
  earth_dist_au REAL, sun_dist_au REAL, apparent_mag REAL, illumination REAL,
  constellation TEXT, PRIMARY KEY (object_id, sample_utc));
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);
CREATE TABLE comet_elements (object_id TEXT PRIMARY KEY REFERENCES objects(id),
  epoch_jd REAL, perihelion_q_au REAL NOT NULL, eccentricity REAL NOT NULL,
  inclination_deg REAL NOT NULL, arg_perihelion_deg REAL NOT NULL,
  node_deg REAL NOT NULL, mag_h REAL, mag_k REAL);
"""

_OBJECTS = [
    ("star:HIP91262", "star", "Vega", "α Lyr"),
    ("NGC1976", "dso", "Orion Nebula", "NGC 1976"),
    ("planet:mars", "planet", "Mars", None),
    ("moon", "moon", "Moon", None),
    ("sun", "sun", "Sun", None),
    ("comet:CK20N020", "comet", "NEOWISE", "C/2020 N2"),
]

# Vega : ra=279.23, dec=+38.78 (au-dessus de l'horizon depuis Paris, été)
# M42 : ra=83.82, dec=-5.39, messier M42
_FIXED = [
    ("star:HIP91262", 279.23, 38.78, 0.03, "star", None, "Lyr", None, None),
    ("NGC1976", 83.82, -5.39, 4.0, "nebula", 85.0, "Ori", "M42", "NGC1976"),
]

# Échantillons journaliers. Mars : ra 149.0→152.0 (+1/j), dec 10.0→13.0 (+1/j)
# sur 08→11 août → à FIX_NOW (09 12:00) ra=150.5, dec=11.5.
def _ephem_rows() -> list[tuple]:
    days = ["2026-08-08", "2026-08-09", "2026-08-10", "2026-08-11"]
    rows: list[tuple] = []
    for i, day in enumerate(days):
        ts = f"{day}T00:00:00Z"
        rows.append(("planet:mars", ts, 149.0 + i, 10.0 + i, 0.5, 1.5, -1.2,
                     None, "Cnc"))
        rows.append(("moon", ts, 200.0 + i, -10.0 + i, None, None, -12.0,
                     0.6 + 0.01 * i, "Vir"))
        rows.append(("sun", ts, 138.0 + i, 16.0 - i, None, None, -26.7,
                     None, "Leo"))
        rows.append(("comet:CK20N020", ts, 45.0 + 2 * i, 20.0 + i, None, None,
                     11.5, None, "Ari"))
    return rows


def build_reference_v2(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.executescript(_SCHEMA)
        con.execute(
            "INSERT INTO meta (schema_version, generated_at, window_start,"
            " window_end, skyfield_kernel) VALUES (?, ?, ?, ?, ?)",
            (2, "2026-08-09T00:00:00Z", "2026-08-08", "2026-10-07", "de421.bsp"),
        )
        con.executemany(
            "INSERT INTO objects (id, kind, name, designation)"
            " VALUES (?, ?, ?, ?)",
            _OBJECTS,
        )
        con.executemany(
            "INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag,"
            " object_type, size_arcmin, constellation, messier, ngc_ic)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _FIXED,
        )
        con.executemany(
            "INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg,"
            " earth_dist_au, sun_dist_au, apparent_mag, illumination,"
            " constellation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _ephem_rows(),
        )
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reference_fixtures.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/reference_fixtures.py backend/tests/test_reference_fixtures.py
git commit -m "test(oracle): fixture reference.sqlite v2 déterministe (SP2 T3)"
```

---

## Task 4: Modèle catalogue (vocabulaire v2, champs additifs)

**Files:**
- Modify: `backend/astro_brain/services/catalog/models.py`
- Modify (test): `backend/tests/test_catalog_models.py`

**Interfaces:**
- Produces:
  - `CatalogKind = Literal["comet", "planet", "moon", "sun", "dso", "star"]`.
  - `CatalogObject` (champs additifs, tous optionnels sauf existants) : ajoute `messier: str | None = None`, `ngc_ic: str | None = None`, `illumination: float | None = None`, `ephemeris_stale: bool = False`. Inchangés : `qualified_id` (**porte désormais `objects.id`**), `kind`, `name`, `designation`, `ra_deg`, `dec_deg`, `mag`, `constellation`, `object_type`, `angular_size_arcmin`, `altitude_deg`, `azimuth_deg`, `extras`.
  - `CatalogFilter` : ajoute `messier_only: bool = False`.

Note : changement **additif**. `SqliteCatalogProvider` (ancien) continue de fonctionner : il ne renseigne pas les nouveaux champs (défauts). Seul `test_catalog_models.py` doit changer si une assertion contraignait l'ancien Literal.

- [ ] **Step 1: Write the failing test**

```python
# ajouter à backend/tests/test_catalog_models.py
from astro_brain.services.catalog.models import CatalogFilter, CatalogObject


def test_catalog_object_accepts_v2_kinds_and_dso_extras() -> None:
    obj = CatalogObject(
        qualified_id="NGC1976",
        kind="dso",
        name="Orion Nebula",
        ra_deg=83.82,
        dec_deg=-5.39,
        messier="M42",
        ngc_ic="NGC1976",
    )
    assert obj.kind == "dso"
    assert obj.messier == "M42"
    assert obj.illumination is None
    assert obj.ephemeris_stale is False


def test_catalog_filter_has_messier_only_default_false() -> None:
    assert CatalogFilter().messier_only is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_models.py -v`
Expected: FAIL (`ValidationError`: `kind` `dso` invalide / champ `messier` inconnu).

- [ ] **Step 3: Write minimal implementation**

Éditer `models.py` :

```python
CatalogKind = Literal["comet", "planet", "moon", "sun", "dso", "star"]
```

Dans `CatalogObject`, après `angular_size_arcmin` :

```python
    messier: str | None = None
    ngc_ic: str | None = None
    illumination: float | None = None
    ephemeris_stale: bool = False
```

Dans `CatalogFilter`, après `max_mag` :

```python
    messier_only: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_models.py tests/test_catalog_sqlite_provider.py tests/test_catalog_routes.py -v`
Expected: PASS (nouveaux + anciens restent verts — `SqliteCatalogProvider` renseigne les défauts).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/models.py backend/tests/test_catalog_models.py
git commit -m "feat(oracle): modèle catalogue vocabulaire v2 + champs messier/ngc/illumination (SP2 T4)"
```

---

## Task 5: `FixedObjectProvider` (dso / star → `fixed_object`)

**Files:**
- Modify: `backend/astro_brain/services/catalog/providers.py`
- Test: `backend/tests/test_fixed_object_provider.py`

**Interfaces:**
- Consumes: `ReferenceDb` (T2), `CatalogFilter`/`CatalogObject` (T4), `build_reference_v2`/`FIX_NOW` (T3).
- Produces:
  - `class FixedObjectProvider`: `KINDS = ("dso", "star")`; `__init__(self, reference: ReferenceDb)`; `async list_objects(self, filter: CatalogFilter) -> list[CatalogObject]`; `async get_object(self, obj_id: str) -> CatalogObject | None`.
  - Requête : join `fixed_object f JOIN objects o ON o.id = f.object_id`. `WHERE o.kind IN ('dso','star')` (ou `= filter.kind` si dans `KINDS`). `max_mag` → `AND f.apparent_mag IS NOT NULL AND f.apparent_mag <= ?`. `messier_only` → `AND f.messier IS NOT NULL`. `search` → `AND (o.name LIKE ? OR o.designation LIKE ? OR f.messier LIKE ? OR f.ngc_ic LIKE ?)`. `ORDER BY CASE WHEN f.apparent_mag IS NULL THEN 1 ELSE 0 END, f.apparent_mag, o.name LIMIT ? OFFSET ?`. `mag` ← `apparent_mag`, `angular_size_arcmin` ← `size_arcmin`. `get_object` : `WHERE f.object_id = ?` (id unique, pas de restriction kind) ; `None` si absent.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fixed_object_provider.py
from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import FixedObjectProvider
from tests.reference_fixtures import build_reference_v2


async def _provider(tmp_path: Path) -> FixedObjectProvider:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return FixedObjectProvider(ref)


async def test_lists_dso_and_star(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter())
    kinds = {o.kind for o in objs}
    assert kinds == {"dso", "star"}
    vega = next(o for o in objs if o.name == "Vega")
    assert vega.qualified_id == "star:HIP91262"
    assert vega.mag == 0.03


async def test_filter_kind_dso_only(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(kind="dso"))
    assert [o.kind for o in objs] == ["dso"]


async def test_messier_only(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(messier_only=True))
    assert all(o.messier is not None for o in objs)
    assert any(o.messier == "M42" for o in objs)


async def test_max_mag_filters_faint(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter(max_mag=1.0))
    assert all(o.mag is not None and o.mag <= 1.0 for o in objs)
    assert {o.name for o in objs} == {"Vega"}


async def test_get_object_by_id(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    m42 = await prov.get_object("NGC1976")
    assert m42 is not None and m42.messier == "M42"
    assert m42.angular_size_arcmin == 85.0
    assert await prov.get_object("planet:mars") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fixed_object_provider.py -v`
Expected: FAIL (`ImportError: cannot import name 'FixedObjectProvider'`).

- [ ] **Step 3: Write minimal implementation**

Ajouter à `providers.py` (garder `SqliteCatalogProvider` en place) :

```python
from astro_brain.repository.reference_db import ReferenceDb

_FIXED_COLUMNS = (
    "o.id, o.kind, o.name, o.designation, f.ra_deg, f.dec_deg, f.apparent_mag,"
    " f.object_type, f.size_arcmin, f.constellation, f.messier, f.ngc_ic"
)


def _fixed_row_to_object(row: tuple[Any, ...]) -> CatalogObject:
    (oid, kind, name, designation, ra, dec, mag, otype, size, const, messier,
     ngc_ic) = row
    return CatalogObject(
        qualified_id=oid,
        kind=kind,
        name=name if name is not None else (designation or oid),
        designation=designation,
        ra_deg=ra,
        dec_deg=dec,
        mag=mag,
        constellation=const,
        object_type=otype,
        angular_size_arcmin=size,
        messier=messier,
        ngc_ic=ngc_ic,
    )


class FixedObjectProvider:
    """Objets fixes (dso, star) lus dans `fixed_object` de reference.sqlite."""

    KINDS = ("dso", "star")

    def __init__(self, reference: ReferenceDb) -> None:
        self._reference = reference

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        conn = self._reference.current()
        if conn is None:
            return []
        sql = f"SELECT {_FIXED_COLUMNS} FROM fixed_object f" \
              " JOIN objects o ON o.id = f.object_id WHERE "
        params: list[Any] = []
        if filter.kind in self.KINDS:
            sql += "o.kind = ?"
            params.append(filter.kind)
        else:
            sql += "o.kind IN ('dso', 'star')"
        if filter.max_mag is not None:
            sql += " AND f.apparent_mag IS NOT NULL AND f.apparent_mag <= ?"
            params.append(filter.max_mag)
        if filter.messier_only:
            sql += " AND f.messier IS NOT NULL"
        if filter.search:
            like = f"%{filter.search}%"
            sql += (" AND (o.name LIKE ? OR o.designation LIKE ?"
                    " OR f.messier LIKE ? OR f.ngc_ic LIKE ?)")
            params.extend([like, like, like, like])
        sql += (" ORDER BY CASE WHEN f.apparent_mag IS NULL THEN 1 ELSE 0 END,"
                " f.apparent_mag, o.name LIMIT ? OFFSET ?")
        params.extend([filter.limit, filter.offset])
        cursor = await conn.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        await cursor.close()
        return [_fixed_row_to_object(r) for r in rows]

    async def get_object(self, obj_id: str) -> CatalogObject | None:
        conn = self._reference.current()
        if conn is None:
            return None
        cursor = await conn.execute(
            f"SELECT {_FIXED_COLUMNS} FROM fixed_object f"
            " JOIN objects o ON o.id = f.object_id WHERE f.object_id = ?",
            (obj_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return _fixed_row_to_object(row) if row is not None else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fixed_object_provider.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/providers.py backend/tests/test_fixed_object_provider.py
git commit -m "feat(oracle): FixedObjectProvider (dso/star depuis reference.sqlite) (SP2 T5)"
```

---

## Task 6: `EphemerisProvider` (comet/planet/moon/sun, interpolé à `now`)

**Files:**
- Modify: `backend/astro_brain/services/catalog/providers.py`
- Test: `backend/tests/test_ephemeris_provider.py`

**Interfaces:**
- Consumes: `ReferenceDb`, `interpolation.interpolate_radec`/`parse_utc` (T1), fixture (T3).
- Produces:
  - `class EphemerisProvider`: `KINDS = ("comet", "planet", "moon", "sun")`; `__init__(self, reference: ReferenceDb, *, now_utc: Callable[[], datetime])`; `async list_objects(filter) -> list[CatalogObject]`; `async get_object(obj_id) -> CatalogObject | None`.
  - **list** : requête sur `sample_utc BETWEEN (now - 1.5j) AND (now + 1.5j)` join `objects` (kind restreint via `KINDS`/`filter.kind`) ; groupe par `object_id` ; pour chaque, prend l'encadrant `before`/`after` de `now` → `interpolate_radec`. Objet **omis** s'il n'a pas d'encadrant (hors fenêtre). Attributs (`mag`←apparent_mag, `illumination`, `constellation`) pris de l'échantillon `before`. Puis filtre `max_mag`/`search` (Python), tri `(mag or +inf, name)`, `limit`/`offset` (Python). `ephemeris_stale=False` (list ne renvoie que du plaçable).
  - **get_object** : tous les échantillons de l'id ; si encadrant présent → interpolé, `ephemeris_stale=False` ; sinon (hors fenêtre) → coords de l'échantillon-frontière le plus proche, `ephemeris_stale=True`. `None` si l'id n'a **aucun** échantillon.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_ephemeris_provider.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import EphemerisProvider
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _provider(tmp_path: Path, now: datetime = FIX_NOW) -> EphemerisProvider:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return EphemerisProvider(ref, now_utc=lambda: now)


async def test_lists_ephemeral_families_interpolated(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    objs = await prov.list_objects(CatalogFilter())
    assert {o.kind for o in objs} == {"comet", "planet", "moon", "sun"}
    mars = next(o for o in objs if o.qualified_id == "planet:mars")
    assert mars.ra_deg == pytest.approx(150.5)   # interpolé à 09 12:00
    assert mars.dec_deg == pytest.approx(11.5)
    assert mars.ephemeris_stale is False


async def test_moon_has_illumination(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    moon = next(o for o in await prov.list_objects(CatalogFilter(kind="moon"))
                if o.qualified_id == "moon")
    assert moon.illumination is not None


async def test_get_object_out_of_window_is_stale(tmp_path: Path) -> None:
    far = datetime(2027, 1, 1, tzinfo=UTC)
    prov = await _provider(tmp_path, now=far)
    mars = await prov.get_object("planet:mars")
    assert mars is not None and mars.ephemeris_stale is True


async def test_list_omits_out_of_window(tmp_path: Path) -> None:
    far = datetime(2027, 1, 1, tzinfo=UTC)
    prov = await _provider(tmp_path, now=far)
    assert await prov.list_objects(CatalogFilter()) == []


async def test_get_object_unknown_id_is_none(tmp_path: Path) -> None:
    prov = await _provider(tmp_path)
    assert await prov.get_object("star:HIP91262") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ephemeris_provider.py -v`
Expected: FAIL (`ImportError: cannot import name 'EphemerisProvider'`).

- [ ] **Step 3: Write minimal implementation**

Ajouter à `providers.py` (imports `from collections.abc import Callable`, `from datetime import datetime, timedelta`, `from astro_brain.services.catalog.interpolation import interpolate_radec, parse_utc`) :

```python
class EphemerisProvider:
    """Objets éphémères (comet/planet/moon/sun), RA/Dec interpolé à `now`."""

    KINDS = ("comet", "planet", "moon", "sun")

    def __init__(
        self, reference: ReferenceDb, *, now_utc: Callable[[], datetime]
    ) -> None:
        self._reference = reference
        self._now_utc = now_utc

    def _kinds_clause(self, filter: CatalogFilter) -> tuple[str, list[Any]]:
        if filter.kind in self.KINDS:
            return "o.kind = ?", [filter.kind]
        placeholders = ", ".join("?" for _ in self.KINDS)
        return f"o.kind IN ({placeholders})", list(self.KINDS)

    async def _rows_for(
        self, conn: aiosqlite.Connection, where: str, params: list[Any]
    ) -> dict[str, list[tuple[Any, ...]]]:
        cursor = await conn.execute(
            "SELECT e.object_id, o.kind, o.name, o.designation, e.sample_utc,"
            " e.ra_deg, e.dec_deg, e.apparent_mag, e.illumination,"
            " e.constellation FROM ephemeris e JOIN objects o"
            f" ON o.id = e.object_id WHERE {where} ORDER BY e.object_id,"
            " e.sample_utc",
            tuple(params),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        grouped: dict[str, list[tuple[Any, ...]]] = {}
        for r in rows:
            grouped.setdefault(r[0], []).append(r)
        return grouped

    def _build(
        self, samples: list[tuple[Any, ...]], now: datetime
    ) -> CatalogObject | None:
        if not samples:
            return None
        parsed = [(parse_utc(s[4]), s) for s in samples]
        before = [p for p in parsed if p[0] <= now]
        after = [p for p in parsed if p[0] >= now]
        stale = not (before and after)
        if not stale:
            b, a = before[-1], after[0]
            ra, dec = interpolate_radec(
                (b[0], b[1][5], b[1][6]), (a[0], a[1][5], a[1][6]), now
            )
            src = b[1]
        else:
            # échantillon-frontière le plus proche de `now`
            src = min(parsed, key=lambda p: abs((p[0] - now).total_seconds()))[1]
            ra, dec = src[5], src[6]
        return CatalogObject(
            qualified_id=src[0],
            kind=src[1],
            name=src[2] if src[2] is not None else (src[3] or src[0]),
            designation=src[3],
            ra_deg=ra,
            dec_deg=dec,
            mag=src[7],
            illumination=src[8],
            constellation=src[9],
            ephemeris_stale=stale,
        )

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        conn = self._reference.current()
        if conn is None:
            return []
        now = self._now_utc()
        clause, params = self._kinds_clause(filter)
        lo = (now - timedelta(days=1, hours=12)).isoformat()
        hi = (now + timedelta(days=1, hours=12)).isoformat()
        where = f"{clause} AND e.sample_utc BETWEEN ? AND ?"
        grouped = await self._rows_for(conn, where, params + [lo, hi])
        objs: list[CatalogObject] = []
        for samples in grouped.values():
            obj = self._build(samples, now)
            if obj is None or obj.ephemeris_stale:
                continue  # list n'affiche que du plaçable
            if filter.max_mag is not None and (
                obj.mag is None or obj.mag > filter.max_mag
            ):
                continue
            if filter.search:
                needle = filter.search.lower()
                hay = f"{obj.name} {obj.designation or ''}".lower()
                if needle not in hay:
                    continue
            objs.append(obj)
        objs.sort(key=lambda o: (o.mag if o.mag is not None else float("inf"),
                                 o.name))
        return objs[filter.offset : filter.offset + filter.limit]

    async def get_object(self, obj_id: str) -> CatalogObject | None:
        conn = self._reference.current()
        if conn is None:
            return None
        now = self._now_utc()
        grouped = await self._rows_for(conn, "e.object_id = ?", [obj_id])
        samples = grouped.get(obj_id)
        if not samples:
            return None
        return self._build(samples, now)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ephemeris_provider.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/providers.py backend/tests/test_ephemeris_provider.py
git commit -m "feat(oracle): EphemerisProvider interpolé à now + gestion hors-fenêtre (SP2 T6)"
```

---

## Task 7: Façade `ReferenceCatalog` (routing + merge + get_by_id)

**Files:**
- Create: `backend/astro_brain/services/catalog/reference_catalog.py`
- Test: `backend/tests/test_reference_catalog.py`

**Interfaces:**
- Consumes: `FixedObjectProvider` (T5), `EphemerisProvider` (T6), `ReferenceDb` (T2), `CatalogFilter`/`CatalogObject`.
- Produces:
  - `class ReferenceCatalog`: `__init__(self, *, fixed: FixedObjectProvider, ephemeris: EphemerisProvider, reference: ReferenceDb)`; `async list_all(self, filter: CatalogFilter) -> list[CatalogObject]`; `async get_by_qualified_id(self, obj_id: str) -> CatalogObject | None`. **Mêmes noms de méthode que l'ancien `CatalogRegistry`** pour que `routes/catalog.py` et `deps.get_catalog_registry` restent inchangés.
  - `list_all` : si `not reference.ready` → `[]`. Si `filter.kind` ∈ fixed → `fixed`. ∈ ephemeris → `ephemeris`. `kind` inconnu non-`None` → `[]`. `kind is None` → interroge les deux avec fenêtre élargie (`limit+offset`, `offset=0`), fusionne, trie `(mag or +inf, name)`, pagine.
  - `get_by_qualified_id` : si `not reference.ready` → `None` ; essaie `fixed.get_object` puis `ephemeris.get_object`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_catalog.py
from __future__ import annotations

from pathlib import Path

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)
from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _catalog(tmp_path: Path) -> ReferenceCatalog:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    return ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )


async def test_list_all_merges_all_families(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    objs = await cat.list_all(CatalogFilter(limit=100))
    assert {o.kind for o in objs} == {"comet", "planet", "moon", "sun", "dso",
                                      "star"}


async def test_list_all_sorted_by_mag(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    mags = [o.mag for o in await cat.list_all(CatalogFilter(limit=100))
            if o.mag is not None]
    assert mags == sorted(mags)


async def test_get_by_id_routes_fixed_and_ephemeris(tmp_path: Path) -> None:
    cat = await _catalog(tmp_path)
    assert (await cat.get_by_qualified_id("NGC1976")).kind == "dso"
    assert (await cat.get_by_qualified_id("planet:mars")).kind == "planet"
    assert await cat.get_by_qualified_id("bogus:id") is None


async def test_not_ready_yields_empty(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    cat = ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )
    assert await cat.list_all(CatalogFilter()) == []
    assert await cat.get_by_qualified_id("NGC1976") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reference_catalog.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/astro_brain/services/catalog/reference_catalog.py
"""Façade catalogue au-dessus des providers fixe/éphémère (reference.sqlite)."""
from __future__ import annotations

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.models import CatalogFilter, CatalogObject
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)


class ReferenceCatalog:
    def __init__(
        self,
        *,
        fixed: FixedObjectProvider,
        ephemeris: EphemerisProvider,
        reference: ReferenceDb,
    ) -> None:
        self._fixed = fixed
        self._ephemeris = ephemeris
        self._reference = reference

    async def list_all(self, filter: CatalogFilter) -> list[CatalogObject]:
        if not self._reference.ready:
            return []
        if filter.kind is not None:
            if filter.kind in self._fixed.KINDS:
                return await self._fixed.list_objects(filter)
            if filter.kind in self._ephemeris.KINDS:
                return await self._ephemeris.list_objects(filter)
            return []
        widened = filter.model_copy(
            update={"limit": filter.limit + filter.offset, "offset": 0}
        )
        merged: list[CatalogObject] = []
        merged.extend(await self._fixed.list_objects(widened))
        merged.extend(await self._ephemeris.list_objects(widened))
        merged.sort(
            key=lambda o: (o.mag if o.mag is not None else float("inf"), o.name)
        )
        return merged[filter.offset : filter.offset + filter.limit]

    async def get_by_qualified_id(self, obj_id: str) -> CatalogObject | None:
        if not self._reference.ready:
            return None
        obj = await self._fixed.get_object(obj_id)
        if obj is not None:
            return obj
        return await self._ephemeris.get_object(obj_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reference_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/reference_catalog.py backend/tests/test_reference_catalog.py
git commit -m "feat(oracle): façade ReferenceCatalog (routing familles + get_by_id) (SP2 T7)"
```

---

## Task 8: `VisibilityEnricher` — gérer `ephemeris_stale`

**Files:**
- Modify: `backend/astro_brain/services/catalog/visibility.py`
- Modify (test): `backend/tests/test_catalog_visibility.py` (créer si absent)

**Interfaces:**
- Produces: comportement inchangé pour les objets normaux ; un objet `ephemeris_stale=True` n'est **jamais enrichi** (alt/az restent `None`) et est **exclu** quand `visible_now=True`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_catalog_visibility.py
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.visibility import VisibilityEnricher


def _enricher() -> VisibilityEnricher:
    return VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35),
        now_utc=lambda: datetime(2026, 6, 21, 22, 0, tzinfo=UTC),
    )


def test_stale_object_not_enriched_and_excluded_when_visible_now() -> None:
    stale = CatalogObject(qualified_id="planet:mars", kind="planet", name="Mars",
                          ra_deg=150.0, dec_deg=11.0, ephemeris_stale=True)
    enr = _enricher()
    kept = enr.enrich([stale], visible_now=False)
    assert kept[0].altitude_deg is None
    assert enr.enrich([stale], visible_now=True) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_visibility.py -v`
Expected: FAIL (l'objet stale est enrichi ou pas exclu).

- [ ] **Step 3: Write minimal implementation**

Dans `visibility.py`, au début de la boucle `for obj in objects:` :

```python
        for obj in objects:
            if obj.ephemeris_stale:
                if visible_now:
                    continue
                enriched.append(obj)
                continue
            az, alt = sky_az_alt_from_ra_dec(obj.ra_deg, obj.dec_deg, observer, t)
            ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_visibility.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/visibility.py backend/tests/test_catalog_visibility.py
git commit -m "feat(oracle): enricher visibilité — objets éphémères hors-fenêtre non enrichis (SP2 T8)"
```

---

## Task 9: `TargetResolver` (id → cible GoTo)

**Files:**
- Create: `backend/astro_brain/services/catalog/resolver.py`
- Test: `backend/tests/test_target_resolver.py`

**Interfaces:**
- Consumes: `ReferenceCatalog` (T7).
- Produces:
  - `@dataclass(frozen=True) class ResolvedTarget: id: str; kind: str; name: str; ra_deg: float; dec_deg: float; stale: bool`.
  - `class TargetResolver`: `__init__(self, catalog: ReferenceCatalog)`; `async resolve(self, obj_id: str) -> ResolvedTarget | None`. `name = obj.name or obj.designation or obj.qualified_id`; `stale = obj.ephemeris_stale`. `None` si l'objet est introuvable.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_target_resolver.py
from __future__ import annotations

from pathlib import Path

import pytest

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.providers import (
    EphemerisProvider,
    FixedObjectProvider,
)
from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
from astro_brain.services.catalog.resolver import TargetResolver
from tests.reference_fixtures import FIX_NOW, build_reference_v2


async def _resolver(tmp_path: Path) -> TargetResolver:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    cat = ReferenceCatalog(
        fixed=FixedObjectProvider(ref),
        ephemeris=EphemerisProvider(ref, now_utc=lambda: FIX_NOW),
        reference=ref,
    )
    return TargetResolver(cat)


async def test_resolve_fixed(tmp_path: Path) -> None:
    r = await (await _resolver(tmp_path)).resolve("NGC1976")
    assert r is not None and r.kind == "dso" and r.name == "Orion Nebula"
    assert r.ra_deg == pytest.approx(83.82)
    assert r.stale is False


async def test_resolve_ephemeris_interpolated(tmp_path: Path) -> None:
    r = await (await _resolver(tmp_path)).resolve("planet:mars")
    assert r is not None and r.ra_deg == pytest.approx(150.5)


async def test_resolve_unknown_is_none(tmp_path: Path) -> None:
    assert await (await _resolver(tmp_path)).resolve("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_target_resolver.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/astro_brain/services/catalog/resolver.py
"""Résolution d'un `id` catalogue en cible GoTo (RA/Dec + kind + nom)."""
from __future__ import annotations

from dataclasses import dataclass

from astro_brain.services.catalog.reference_catalog import ReferenceCatalog


@dataclass(frozen=True)
class ResolvedTarget:
    id: str
    kind: str
    name: str
    ra_deg: float
    dec_deg: float
    stale: bool


class TargetResolver:
    def __init__(self, catalog: ReferenceCatalog) -> None:
        self._catalog = catalog

    async def resolve(self, obj_id: str) -> ResolvedTarget | None:
        obj = await self._catalog.get_by_qualified_id(obj_id)
        if obj is None:
            return None
        return ResolvedTarget(
            id=obj.qualified_id,
            kind=obj.kind,
            name=obj.name or obj.designation or obj.qualified_id,
            ra_deg=obj.ra_deg,
            dec_deg=obj.dec_deg,
            stale=obj.ephemeris_stale,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_target_resolver.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/catalog/resolver.py backend/tests/test_target_resolver.py
git commit -m "feat(oracle): TargetResolver id → cible GoTo (SP2 T9)"
```

---

## Task 10: `ReferenceSync` (fetch conditionnel, verify, swap atomique)

**Files:**
- Create: `backend/astro_brain/services/reference/__init__.py` (vide)
- Create: `backend/astro_brain/services/reference/sync.py`
- Test: `backend/tests/test_reference_sync.py`

**Interfaces:**
- Consumes: `ReferenceDb` (T2), `local_sha256`, `SUPPORTED_SCHEMA_VERSION`, httpx.
- Produces:
  - `@dataclass(frozen=True) class SyncResult: status: Literal["updated","up_to_date","offline","rejected_schema","rejected_hash"]; schema_version: int | None = None`.
  - `class ReferenceSync`: `__init__(self, *, reference: ReferenceDb, manifest_url: str, client_factory: Callable[[], httpx.AsyncClient] | None = None)`; `async sync(self) -> SyncResult`.
  - Étapes : GET manifest (erreur réseau → `offline`) ; `schema_version > SUPPORTED` → `rejected_schema` (cache gardé) ; `sqlite_sha256 == local_sha256(reference.path)` → `up_to_date` ; sinon GET `sqlite_url` (stream → temp `<path>.tmp`) ; `sha256(temp) != manifest` → `rejected_hash` (temp supprimé) ; ouvrir temp et vérifier `meta.schema_version <= SUPPORTED` (sinon `rejected_schema`, temp supprimé) ; `os.replace(temp, reference.path)` ; `await reference.reopen()` ; `updated`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_sync.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from astro_brain.repository.reference_db import ReferenceDb, local_sha256
from astro_brain.services.reference.sync import ReferenceSync
from tests.reference_fixtures import build_reference_v2


def _sqlite_bytes(tmp_path: Path) -> bytes:
    p = tmp_path / "src.sqlite"
    build_reference_v2(p)
    return p.read_bytes()


def _client_factory(manifest: dict, sqlite: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("manifest.json"):
            return httpx.Response(200, json=manifest)
        return httpx.Response(200, content=sqlite)

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_updated_downloads_and_swaps(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    sha = hashlib.sha256(data).hexdigest()
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite", "sqlite_sha256": sha,
                "window_start": "2026-08-08", "window_end": "2026-10-07"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    result = await sync.sync()
    assert result.status == "updated"
    assert local_sha256(ref.path) == sha
    assert ref.ready is True
    await ref.close()


async def test_up_to_date_when_sha_matches(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    sha = hashlib.sha256(data).hexdigest()
    p = tmp_path / "reference.sqlite"
    p.write_bytes(data)
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite", "sqlite_sha256": sha,
                "window_start": "2026-08-08", "window_end": "2026-10-07"}
    ref = ReferenceDb(p)
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    assert (await sync.sync()).status == "up_to_date"
    await ref.close()


async def test_offline_keeps_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(
        reference=ref, manifest_url="https://h/manifest.json",
        client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)),
    )
    assert (await sync.sync()).status == "offline"


async def test_rejects_future_schema(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    manifest = {"schema_version": 3, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite",
                "sqlite_sha256": hashlib.sha256(data).hexdigest(),
                "window_start": "x", "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    result = await sync.sync()
    assert result.status == "rejected_schema"
    assert local_sha256(ref.path) is None  # rien n'a été écrit


async def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    data = _sqlite_bytes(tmp_path)
    manifest = {"schema_version": 2, "generated_at": "x",
                "sqlite_url": "https://h/reference.sqlite",
                "sqlite_sha256": "deadbeef", "window_start": "x",
                "window_end": "y"}
    ref = ReferenceDb(tmp_path / "reference.sqlite")
    await ref.open()
    sync = ReferenceSync(reference=ref, manifest_url="https://h/manifest.json",
                         client_factory=_client_factory(manifest, data))
    assert (await sync.sync()).status == "rejected_hash"
    assert local_sha256(ref.path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reference_sync.py -v`
Expected: FAIL (`ModuleNotFoundError: astro_brain.services.reference.sync`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/astro_brain/services/reference/__init__.py
```
```python
# backend/astro_brain/services/reference/sync.py
"""Sync de `reference.sqlite` : fetch conditionnel (sha256), verify, swap atomique.

Online-first, non bloquant : toute erreur réseau garde le cache courant.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import httpx

from astro_brain.repository.reference_db import (
    SUPPORTED_SCHEMA_VERSION,
    ReferenceDb,
    local_sha256,
)

logger = logging.getLogger(__name__)

_Status = Literal["updated", "up_to_date", "offline", "rejected_schema",
                  "rejected_hash"]


@dataclass(frozen=True)
class SyncResult:
    status: _Status
    schema_version: int | None = None


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=60.0, follow_redirects=True)


class ReferenceSync:
    def __init__(
        self,
        *,
        reference: ReferenceDb,
        manifest_url: str,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._reference = reference
        self._manifest_url = manifest_url
        self._client_factory = client_factory or _default_client

    def _temp_schema_version(self, path) -> int | None:
        con = sqlite3.connect(path)
        try:
            cur = con.execute("SELECT schema_version FROM meta LIMIT 1")
            row = cur.fetchone()
        except sqlite3.DatabaseError:
            return None
        finally:
            con.close()
        return int(row[0]) if row is not None else None

    async def sync(self) -> SyncResult:
        try:
            async with self._client_factory() as client:
                resp = await client.get(self._manifest_url)
                resp.raise_for_status()
                manifest = resp.json()
                sv = int(manifest["schema_version"])
                if sv > SUPPORTED_SCHEMA_VERSION:
                    logger.warning("reference: schema_version %s > %s, gardé cache",
                                   sv, SUPPORTED_SCHEMA_VERSION)
                    return SyncResult("rejected_schema", sv)
                sha = manifest["sqlite_sha256"]
                if local_sha256(self._reference.path) == sha:
                    return SyncResult("up_to_date", sv)
                dl = await client.get(manifest["sqlite_url"])
                dl.raise_for_status()
                data = dl.content
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("reference: sync offline/invalide (%s)", exc)
            return SyncResult("offline")

        if hashlib.sha256(data).hexdigest() != sha:
            logger.warning("reference: sha256 mismatch, rejet")
            return SyncResult("rejected_hash")

        tmp = self._reference.path.with_suffix(".sqlite.tmp")
        tmp.write_bytes(data)
        tmp_sv = self._temp_schema_version(tmp)
        if tmp_sv is None or tmp_sv > SUPPORTED_SCHEMA_VERSION:
            tmp.unlink(missing_ok=True)
            return SyncResult("rejected_schema", tmp_sv)
        os.replace(tmp, self._reference.path)
        await self._reference.reopen()
        return SyncResult("updated", sv)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reference_sync.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/reference backend/tests/test_reference_sync.py
git commit -m "feat(oracle): ReferenceSync fetch conditionnel + verify + swap atomique (SP2 T10)"
```

---

## Task 11: Routes référence (`GET /reference/status`, `POST /reference/sync`)

**Files:**
- Create: `backend/astro_brain/routes/reference.py`
- Modify: `backend/astro_brain/deps.py`
- Test: `backend/tests/test_reference_routes.py`

**Interfaces:**
- Consumes: `ReferenceDb`, `ReferenceSync`.
- Produces:
  - `deps.get_reference_db(request) -> ReferenceDb` (`request.app.state.reference_db`), `deps.get_reference_sync(request) -> ReferenceSync` (`request.app.state.reference_sync`).
  - `GET /reference/status` → `{ready: bool, schema_version: int|None, generated_at: str|None, window_start: str|None, window_end: str|None}`.
  - `POST /reference/sync` → `{status: str, schema_version: int|None}` (résultat de `ReferenceSync.sync()`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reference_routes.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.routes.reference import router
from astro_brain.services.reference.sync import ReferenceSync, SyncResult
from tests.reference_fixtures import build_reference_v2


class _FakeSync(ReferenceSync):
    def __init__(self) -> None:  # pas d'I/O
        pass

    async def sync(self) -> SyncResult:
        return SyncResult("up_to_date", 2)


def _client(ref: ReferenceDb) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.reference_db = ref
    app.state.reference_sync = _FakeSync()
    return TestClient(app)


async def test_status_ready(tmp_path: Path) -> None:
    p = tmp_path / "reference.sqlite"
    build_reference_v2(p)
    ref = ReferenceDb(p)
    await ref.open()
    r = _client(ref).get("/reference/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True
    assert body["schema_version"] == 2
    assert body["window_end"] == "2026-10-07"
    await ref.close()


async def test_status_not_ready(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    r = _client(ref).get("/reference/status")
    assert r.json() == {"ready": False, "schema_version": None,
                        "generated_at": None, "window_start": None,
                        "window_end": None}


async def test_post_sync_returns_status(tmp_path: Path) -> None:
    ref = ReferenceDb(tmp_path / "absent.sqlite")
    await ref.open()
    r = _client(ref).post("/reference/sync")
    assert r.status_code == 200
    assert r.json() == {"status": "up_to_date", "schema_version": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reference_routes.py -v`
Expected: FAIL (`ModuleNotFoundError: astro_brain.routes.reference`).

- [ ] **Step 3: Write minimal implementation**

Ajouter à `deps.py` :

```python
def get_reference_db(request: Request) -> Any:
    return request.app.state.reference_db


def get_reference_sync(request: Request) -> Any:
    return request.app.state.reference_sync
```

```python
# backend/astro_brain/routes/reference.py
"""Routes de l'artefact de référence : statut + déclenchement de sync."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.reference.sync import ReferenceSync

router = APIRouter(tags=["reference"], prefix="/reference")


class ReferenceStatus(BaseModel):
    ready: bool
    schema_version: int | None = None
    generated_at: str | None = None
    window_start: str | None = None
    window_end: str | None = None


class SyncResponse(BaseModel):
    status: str
    schema_version: int | None = None


@router.get("/status", response_model=ReferenceStatus)
async def reference_status(
    reference: ReferenceDb = Depends(deps.get_reference_db),
) -> ReferenceStatus:
    meta = await reference.meta()
    if meta is None:
        return ReferenceStatus(ready=False)
    return ReferenceStatus(
        ready=reference.ready,
        schema_version=meta.schema_version,
        generated_at=meta.generated_at,
        window_start=meta.window_start,
        window_end=meta.window_end,
    )


@router.post("/sync", response_model=SyncResponse)
async def reference_sync(
    sync: ReferenceSync = Depends(deps.get_reference_sync),
) -> SyncResponse:
    result = await sync.sync()
    return SyncResponse(status=result.status, schema_version=result.schema_version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reference_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/routes/reference.py backend/astro_brain/deps.py backend/tests/test_reference_routes.py
git commit -m "feat(oracle): routes GET /reference/status + POST /reference/sync (SP2 T11)"
```

---

## Task 12: Route catalogue — paramètre `messier`

**Files:**
- Modify: `backend/astro_brain/routes/catalog.py`
- Modify (test): `backend/tests/test_catalog_routes.py`

**Interfaces:**
- Consumes: `CatalogFilter.messier_only` (T4).
- Produces: `GET /catalog/objects?messier=true` → `CatalogFilter(messier_only=True)`. Reste inchangé (`kind`, `search`, `max_mag`, `visible_now`, `limit`, `offset`, l'enveloppe et `get_by_qualified_id`).

- [ ] **Step 1: Write the failing test**

```python
# ajouter à backend/tests/test_catalog_routes.py
def test_list_objects_propagates_messier_flag() -> None:
    registry = AsyncMock()
    registry.list_all = AsyncMock(return_value=[])
    client = _build_client(registry)

    r = client.get("/catalog/objects", params={"messier": "true"})

    assert r.status_code == 200
    f = registry.list_all.await_args.args[0]
    assert f.messier_only is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_routes.py::test_list_objects_propagates_messier_flag -v`
Expected: FAIL (`messier_only` reste `False`).

- [ ] **Step 3: Write minimal implementation**

Dans `routes/catalog.py`, signature de `list_objects` : ajouter `messier: bool = Query(default=False)` après `max_mag`. Dans la construction du filtre :

```python
    f = CatalogFilter(
        kind=kind, search=search, max_mag=max_mag, messier_only=messier,
        limit=limit, offset=offset,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_routes.py -v`
Expected: PASS (nouveaux + anciens).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/routes/catalog.py backend/tests/test_catalog_routes.py
git commit -m "feat(oracle): GET /catalog/objects filtre messier=true (SP2 T12)"
```

---

## Task 13: Route GoTo — contrat id-only + gardes

**Files:**
- Modify: `backend/astro_brain/routes/goto.py`
- Modify: `backend/astro_brain/deps.py` (ajouter `get_resolver`)
- Rewrite (test): `backend/tests/test_goto_routes.py`

**Interfaces:**
- Consumes: `TargetResolver`/`ResolvedTarget` (T9), `MountService.goto_radec`, `AlignmentService.is_aligned`, `StateBus`.
- Produces:
  - `deps.get_resolver(request) -> TargetResolver` (`request.app.state.resolver`).
  - `GotoRequest(BaseModel): id: str; confirm_solar: bool = False`.
  - `POST /goto` gardes (ordre) : le resolver est indisponible/`None` → tenter résolution ; **si `resolver` absent ou base non prête → 409 `reference_unavailable`** ; `resolve()` `None` → **404 `unknown_id`** ; `target.stale` → **409 `ephemeris_stale`** ; `not is_aligned` → **409 `not_aligned`** ; `goto_in_progress` → **409 `goto_in_progress`** ; `target.kind == "sun"` et `not confirm_solar` → **409 `solar_ack_required`**. Puis `await mount.goto_radec(target.ra_deg, target.dec_deg, target_name=target.name)`. `detail` = le slug listé.

Note : `reference_unavailable` détecté via une méthode du resolver ou l'état `ReferenceDb`. Le resolver expose déjà `resolve()`→`None` pour introuvable ; pour distinguer « base absente » de « id inconnu », la route lit `deps.get_reference_db().ready` en amont. Injecter `reference: ReferenceDb = Depends(deps.get_reference_db)`.

- [ ] **Step 1: Write the failing test** (réécriture complète du fichier)

```python
# backend/tests/test_goto_routes.py
"""Tests /goto : contrat id-only + gardes (reference/unknown/stale/aligned/solar)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.goto import router
from astro_brain.services.catalog.resolver import ResolvedTarget
from astro_brain.services.fakes import FakeMount
from astro_brain.subsystems import SubsystemState


class _Alignment:
    def __init__(self, aligned: bool) -> None:
        self._aligned = aligned

    @property
    def is_aligned(self) -> bool:
        return self._aligned


class _Ref:
    def __init__(self, ready: bool) -> None:
        self.ready = ready


class _Resolver:
    def __init__(self, target: ResolvedTarget | None) -> None:
        self._target = target

    async def resolve(self, obj_id: str) -> ResolvedTarget | None:
        return self._target


def _client(*, aligned=True, ready=True, target=None, in_progress=False):
    bus = StateBus()
    mount = FakeMount(bus)
    if in_progress:
        bus.publish("mount", SubsystemState(
            state="moving", details={"goto_in_progress": True}))
    app = FastAPI()
    app.include_router(router)
    app.state.bus = bus
    app.state.mount = mount
    app.state.alignment = _Alignment(aligned)
    app.state.reference_db = _Ref(ready)
    app.state.resolver = _Resolver(target)
    return TestClient(app), mount


_M42 = ResolvedTarget(id="NGC1976", kind="dso", name="Orion Nebula",
                      ra_deg=83.82, dec_deg=-5.39, stale=False)
_SUN = ResolvedTarget(id="sun", kind="sun", name="Sun", ra_deg=138.0,
                      dec_deg=16.0, stale=False)
_STALE = ResolvedTarget(id="planet:mars", kind="planet", name="Mars",
                        ra_deg=150.0, dec_deg=11.0, stale=True)


def test_goto_ok_calls_mount_with_resolved_coords():
    client, mount = _client(target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 200
    assert mount.goto_calls == [(83.82, -5.39, "Orion Nebula")]


def test_reference_unavailable_409():
    client, mount = _client(ready=False, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "reference_unavailable"
    assert mount.goto_calls == []


def test_unknown_id_404():
    client, _ = _client(target=None)
    r = client.post("/goto", json={"id": "nope"})
    assert r.status_code == 404 and r.json()["detail"] == "unknown_id"


def test_ephemeris_stale_409():
    client, _ = _client(target=_STALE)
    r = client.post("/goto", json={"id": "planet:mars"})
    assert r.status_code == 409 and r.json()["detail"] == "ephemeris_stale"


def test_not_aligned_409():
    client, _ = _client(aligned=False, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "not_aligned"


def test_goto_in_progress_409():
    client, _ = _client(in_progress=True, target=_M42)
    r = client.post("/goto", json={"id": "NGC1976"})
    assert r.status_code == 409 and r.json()["detail"] == "goto_in_progress"


def test_solar_requires_ack():
    client, mount = _client(target=_SUN)
    r = client.post("/goto", json={"id": "sun"})
    assert r.status_code == 409 and r.json()["detail"] == "solar_ack_required"
    assert mount.goto_calls == []
    ok = client.post("/goto", json={"id": "sun", "confirm_solar": True})
    assert ok.status_code == 200
    assert mount.goto_calls == [(138.0, 16.0, "Sun")]


def test_missing_id_422():
    client, _ = _client(target=_M42)
    assert client.post("/goto", json={}).status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_goto_routes.py -v`
Expected: FAIL (ancien contrat `ra_deg`/`dec_deg`).

- [ ] **Step 3: Write minimal implementation**

`deps.py` :

```python
def get_resolver(request: Request) -> Any:
    return request.app.state.resolver
```

`routes/goto.py` (réécriture du corps) :

```python
"""Route REST GoTo : POST /goto (résolution par id + slew sur monture alignée)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.api_models import OkResponse
from astro_brain.bus import StateBus
from astro_brain.repository.reference_db import ReferenceDb
from astro_brain.services.catalog.resolver import TargetResolver
from astro_brain.services.interfaces import AlignmentService, MountService

router = APIRouter(tags=["goto"])


class GotoRequest(BaseModel):
    id: str
    confirm_solar: bool = False


@router.post("/goto", response_model=OkResponse)
async def goto(
    req: GotoRequest,
    mount: MountService = Depends(deps.get_mount),
    alignment: AlignmentService = Depends(deps.get_alignment_service),
    resolver: TargetResolver = Depends(deps.get_resolver),
    reference: ReferenceDb = Depends(deps.get_reference_db),
    bus: StateBus = Depends(deps.get_bus),
) -> OkResponse:
    if not reference.ready:
        raise HTTPException(status_code=409, detail="reference_unavailable")
    target = await resolver.resolve(req.id)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown_id")
    if target.stale:
        raise HTTPException(status_code=409, detail="ephemeris_stale")
    if not alignment.is_aligned:
        raise HTTPException(status_code=409, detail="not_aligned")
    mount_state = bus.get_full_state().subsystems.get("mount")
    if mount_state is not None and mount_state.details.get("goto_in_progress"):
        raise HTTPException(status_code=409, detail="goto_in_progress")
    if target.kind == "sun" and not req.confirm_solar:
        raise HTTPException(status_code=409, detail="solar_ack_required")
    await mount.goto_radec(target.ra_deg, target.dec_deg, target_name=target.name)
    return OkResponse()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_goto_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/routes/goto.py backend/astro_brain/deps.py backend/tests/test_goto_routes.py
git commit -m "feat(oracle): GoTo id-only + gardes reference/stale/solar (SP2 T13)"
```

---

## Task 14: Bascule — câblage `app.py`, migration `_004`, suppression de l'ancienne source

**Files:**
- Create: `backend/astro_brain/repository/migrations/_004_drop_catalog_objects.py`
- Modify: `backend/astro_brain/app.py`
- Modify (tests): `backend/tests/test_app.py`
- Delete: `backend/astro_brain/data/seed_stars.sql`, `backend/astro_brain/tools/seed_stars.py`, `backend/astro_brain/services/catalog/seed_runner.py`, `backend/astro_brain/services/catalog/registry.py`, `SqliteCatalogProvider` (+ `_SELECT_COLUMNS`/`_row_to_object` devenus inutiles) dans `providers.py`
- Delete (tests): `backend/tests/test_catalog_seed_runner.py`, `backend/tests/test_catalog_seed_stars_smoke.py`, `backend/tests/test_seed_stars_tool.py`, `backend/tests/test_catalog_sqlite_provider.py`, `backend/tests/test_catalog_registry.py`

**Interfaces:**
- Consumes: tout le stack T1→T13.
- Produces:
  - Migration `_004` : `VERSION = 4`, `SQL = "DROP TABLE IF EXISTS catalog_objects;"`.
  - `build_app(..., sync_on_boot: bool | None = None)` : wiring référence sur `app.state.reference_db`, `app.state.reference_sync`, `app.state.catalog_registry` (= `ReferenceCatalog`), `app.state.resolver` (= `TargetResolver`) ; `app.include_router(reference_router)` ; tâche de fond sync au boot si `sync_on_boot` (défaut = env `ASTRO_BRAIN_REFERENCE_SYNC_ON_BOOT != "0"`) ; **retrait** de `apply_seeds` et du provider `star`/`state.db`.

- [ ] **Step 1: Migration + test**

Créer `_004_drop_catalog_objects.py` :

```python
"""Retire la table `catalog_objects` : le catalogue vient désormais de
`reference.sqlite` (SP2). Forward-only."""
from __future__ import annotations

VERSION = 4

SQL = """
DROP TABLE IF EXISTS catalog_objects;
"""
```

Ajouter à `backend/tests/test_state_db.py` :

```python
async def test_migration_004_drops_catalog_objects(tmp_path) -> None:
    import aiosqlite
    from astro_brain.repository.state_db import run_migrations
    conn = await aiosqlite.connect(":memory:")
    await run_migrations(conn)
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name='catalog_objects'"
    )
    assert await cur.fetchone() is None
    await cur.close()
    cur = await conn.execute("SELECT MAX(version) FROM schema_version")
    assert (await cur.fetchone())[0] >= 4
    await cur.close()
    await conn.close()
```

- [ ] **Step 2: Run migration test (fails)**

Run: `uv run pytest "tests/test_state_db.py::test_migration_004_drops_catalog_objects" -v`
Expected: FAIL (version < 4 / table présente).

- [ ] **Step 3: Rewire `app.py` + delete old source**

Dans `app.py` :
- Retirer les imports `apply_seeds`, `SqliteCatalogProvider`, `CatalogRegistry`, et l'import `as_file, files` s'il ne sert plus qu'aux seeds.
- Ajouter :
  ```python
  from astro_brain.repository.reference_db import (
      ReferenceDb, manifest_url, reference_path,
  )
  from astro_brain.routes.reference import router as reference_router
  from astro_brain.services.catalog.providers import (
      EphemerisProvider, FixedObjectProvider,
  )
  from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
  from astro_brain.services.catalog.resolver import TargetResolver
  from astro_brain.services.reference.sync import ReferenceSync
  ```
- Signature : `def build_app(*, use_hardware=None, db_path_override=None, sync_on_boot=None)`.
- Dans le lifespan, **remplacer** le bloc seeds + provider star par :
  ```python
  # base référence (reference.sqlite) — fichier distinct, RO, jetable
  if db_path_override in (None, ":memory:") or str(target) == ":memory:":
      ref_path = reference_path()
  else:
      ref_path = Path(target).parent / "reference.sqlite"
  reference_db = ReferenceDb(ref_path)
  await reference_db.open()
  _app.state.reference_db = reference_db

  fixed = FixedObjectProvider(reference_db)
  ephemeris = EphemerisProvider(reference_db, now_utc=lambda: datetime.now(UTC))
  catalog = ReferenceCatalog(fixed=fixed, ephemeris=ephemeris,
                             reference=reference_db)
  _app.state.catalog_registry = catalog
  _app.state.resolver = TargetResolver(catalog)

  reference_sync = ReferenceSync(reference=reference_db,
                                 manifest_url=manifest_url())
  _app.state.reference_sync = reference_sync

  do_sync = (sync_on_boot if sync_on_boot is not None
             else os.environ.get("ASTRO_BRAIN_REFERENCE_SYNC_ON_BOOT", "1") != "0")
  if do_sync:
      background_tasks.append(
          asyncio.create_task(reference_sync.sync(), name="reference-boot-sync")
      )
  ```
- Dans le teardown, ajouter `await reference_db.close()` avant `await db_conn.close()`.
- `app.include_router(reference_router)` dans la section include.
- Supprimer les fichiers : `data/seed_stars.sql`, `tools/seed_stars.py`, `services/catalog/seed_runner.py`, `services/catalog/registry.py`, et retirer de `providers.py` `SqliteCatalogProvider` + `_SELECT_COLUMNS` + `_row_to_object` (garder `CatalogProvider` Protocol s'il est encore importé ailleurs — sinon le retirer aussi).
- Supprimer les tests obsolètes : `test_catalog_seed_runner.py`, `test_catalog_seed_stars_smoke.py`, `test_seed_stars_tool.py`, `test_catalog_sqlite_provider.py`, `test_catalog_registry.py`.

Mettre à jour `test_app.py` :
- Les 6 tests `build_app(...)` : ajouter `sync_on_boot=False`.
- Remplacer `test_build_app_exposes_catalog_registry` par :
  ```python
  def test_build_app_exposes_catalog_and_reference(tmp_path) -> None:
      from astro_brain.app import build_app
      from astro_brain.services.catalog.reference_catalog import ReferenceCatalog
      app = build_app(use_hardware=False, sync_on_boot=False,
                      db_path_override=tmp_path / "state.db")
      with TestClient(app):
          assert isinstance(app.state.catalog_registry, ReferenceCatalog)
          assert app.state.reference_db is not None
          assert app.state.resolver is not None
  ```
- `test_catalog_objects_route_is_registered` : ajouter `sync_on_boot=False` ; l'assertion reste (`objects`/`count` présents, liste vide sans cache → OK).

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: PASS — aucun import cassé, migration `_004` appliquée, `test_app` vert, tests obsolètes supprimés. Vérifier aussi `uv run ruff check .` si le repo l'utilise (imports inutilisés retirés).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(oracle): bascule catalogue vers reference.sqlite — wiring app + migration _004 + retrait seeds (SP2 T14)"
```

- [ ] **Step 6: Journal**

Mettre à jour `docs/project/journal.md` (session courante) : bascule SP2 livrée, backend consommateur de `reference.sqlite`, GoTo id-only, garde solaire, sync online-first. Commit docs séparé.

---

## Self-Review

**1. Spec coverage** (design `2026-08-09-oracle-sp2-backend-design.md`) :
- Bascule catalogue toutes familles → T5/T6/T7 + T14. ✅
- GoTo par id → T9/T13. ✅
- Garde solaire (verrou backend) → T13. ✅
- `id` vocabulaire partagé (`qualified_id` porte `objects.id`) → T4/T5/T6. ✅
- Fichier séparé + connexion RO, pas d'ATTACH → T2/T14. ✅
- Sync online-first non bloquante, pas de bundle → T10 + tâche de fond T14. ✅
- Cache vide `reference_ready=false` → T2/T7 (liste vide) + T13 (409). ✅
- Garde de version `SUPPORTED_SCHEMA_VERSION=2` → T2 (open) + T10 (sync). ✅
- Interpolation linéaire + wrap RA + hors-fenêtre → T1/T6. ✅
- Champs `messier`/`ngc_ic`/`illumination` + filtre Messier → T4/T5/T12. ✅
- `visible_now` = alt>0 inchangé + gestion stale → T8. ✅
- Endpoints `POST /reference/sync` + statut (`GET /reference/status`, question 1 tranchée) → T11. ✅
- Migration `_004` DROP `catalog_objects` + suppression seeds/tools/tests → T14. ✅
- Wizard 3 étoiles laissé tel quel (backlog) → non touché. ✅

**2. Placeholder scan** : aucun TODO/TBD ; chaque étape porte du code exécutable. ✅

**3. Type consistency** :
- `ReferenceCatalog` expose `list_all` / `get_by_qualified_id` (mêmes noms que l'ancien registry consommé par `routes/catalog.py` et `deps.get_catalog_registry`) → route inchangée hors `messier`. ✅
- `qualified_id` conservé partout (pas de renommage `id`), `angular_size_arcmin` ← `size_arcmin`, `mag` ← `apparent_mag` — cohérent T4→T14. ✅
- `KINDS` attribut de classe utilisé par `ReferenceCatalog` (T7) et défini en T5/T6. ✅
- `ResolvedTarget` champs (`id/kind/name/ra_deg/dec_deg/stale`) cohérents T9 ↔ T13. ✅
- `SyncResult.status` littéraux cohérents T10 ↔ T11. ✅

**4. Risque identifié** : les tests async supposent `asyncio_mode=auto`. Vérifier dans `pyproject.toml`/`pytest.ini` au démarrage de T2 ; si absent, ajouter `pytestmark = pytest.mark.asyncio` en tête des nouveaux fichiers de test async (ou activer le mode auto — décision au moment de l'exécution).
