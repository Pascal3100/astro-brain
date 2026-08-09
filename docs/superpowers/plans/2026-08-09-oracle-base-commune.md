# Oracle SP1 — `reference.sqlite` v2, base catalogue commune — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre le producteur `oracle/` (aujourd'hui comètes seules) pour qu'il fabrique une base catalogue **commune** — comètes + planètes + Lune + Soleil + deep-sky (Messier + NGC/IC) + étoiles nommées — sous un schéma unifié versionné `schema_version = 2`.

**Architecture:** Deux natures d'objets, un seul artefact. Les *fixes* (deep-sky, étoiles) reçoivent **une** position RA/Dec of-date ; les *éphémères* (comètes, planètes, Lune, Soleil) reçoivent une **éphéméride pré-calculée** (samples journaliers, fenêtre glissante 60 j). Un modèle de données unique (`records.py`), un writer unique (`build_db.py`), trois sources fetchables (comètes/deep-sky/étoiles, chacune avec fallback bundlé) plus une source no-fetch (kernel `de421.bsp` pour planètes/luminaires).

**Tech Stack:** Python 3.13, `uv`, skyfield ≥1.49, pandas ≥2.2, `sqlite3` stdlib, pytest ≥8. Aucune dépendance vers `backend/` ni `app/`.

## Global Constraints

- **Zéro dépendance vers le Pi / `backend/` / `app/`** — `oracle/` reste autonome ; les consommateurs ne l'importent jamais.
- **Déterminisme offline en test** : kernel `de421.bsp` committé + snapshots fallback committés → aucun réseau pendant les tests.
- **Le fetch ne casse jamais le build** : chaque source fetchable retombe sur un snapshot bundlé via le helper partagé `oracle.sources._fetch.fetch_with_fallback` (une seule implémentation du patron fetch+fallback).
- **RA/Dec stockées en apparent / of-date (JNow)**, jamais J2000/ICRS — via `.apparent().radec(epoch="date")` (éphémères) ou projection `Star` → of-date (fixes).
- **Échantillonnage quotidien, fenêtre roulante 60 jours** pour tous les éphémères.
- **`meta.schema_version = 2`** ; incrémenté à toute évolution de schéma.
- **Base complète et tube-agnostique** : aucun pré-filtre magnitude/taille/type côté producteur. Exclusions volontaires uniquement : Pluton (hors `de421`, mag ~14) et types OpenNGC non-physiques (`Dup`, `NonEx`, `Other`).
- **PEP-compliant** : PEP 8, PEP 257 (docstrings), PEP 484/604 (`X | None`).
- **Commandes** : depuis `oracle/`. Les tests se lancent avec `uv run pytest tests/` (pas de `testpaths` configuré — passer `tests/` explicitement).
- **Convention `sample_utc`** : ISO-8601 UTC, suffixe `Z` (`.isoformat().replace("+00:00", "Z")`).

---

### Task 1: Modèle de données unifié + schéma v2 + writer

Introduit le modèle de sortie partagé (`records.py`), réécrit `schema.sql` en v2, réécrit `build_db.py` en writer unifié, et met à jour le compute comète (`ephemeris.py`) pour émettre la nouvelle `EphemRow`. C'est la fondation : toutes les tâches suivantes produisent des `records` que ce writer consomme.

**Files:**
- Create: `oracle/oracle/records.py`
- Modify: `oracle/schema.sql` (réécriture complète)
- Modify: `oracle/oracle/build_db.py` (réécriture du writer, `SCHEMA_VERSION = 2`)
- Modify: `oracle/oracle/compute/ephemeris.py` (nouvelle `EphemRow`, `object_id`, `apparent_mag`, `illumination`)
- Modify: `oracle/oracle/sources/comets.py` (ajout adaptateur `comet_objects`)
- Test: `oracle/tests/test_records.py` (create)
- Test: `oracle/tests/test_build_db.py` (réécriture)
- Test: `oracle/tests/test_ephemeris.py` (mise à jour des champs)

**Interfaces:**
- Produces:
  - `records.ObjectRow(id: str, kind: str, name: str | None, designation: str | None)`
  - `records.FixedRow(object_id: str, ra_deg: float, dec_deg: float, apparent_mag: float | None, object_type: str | None, size_arcmin: float | None, constellation: str | None, messier: str | None, ngc_ic: str | None)`
  - `records.EphemRow(object_id: str, sample_utc: str, ra_deg: float, dec_deg: float, earth_dist_au: float | None, sun_dist_au: float | None, apparent_mag: float | None, illumination: float | None, constellation: str | None)`
  - `records.CometElements(object_id: str, epoch_jd: float | None, perihelion_q_au: float, eccentricity: float, inclination_deg: float, arg_perihelion_deg: float, node_deg: float, mag_h: float | None, mag_k: float | None)`
  - `build_db.SCHEMA_VERSION: int = 2`
  - `build_db.BuildMeta(schema_version, generated_at, mpc_epoch, window_start, window_end, skyfield_kernel)` (inchangé)
  - `build_db.build_reference_db(out_path: Path, objects: list[ObjectRow], fixed: list[FixedRow], ephem: list[EphemRow], comet_elements: list[CometElements], meta: BuildMeta) -> Path`
  - `build_db._opt(row: pd.Series, key: str) -> float | None` (inchangé, réutilisé)
  - `compute.ephemeris.compute_ephemeris(comets, kernel_path, start_utc, days=60) -> list[EphemRow]` (émet la nouvelle `EphemRow`)
  - `compute.ephemeris.predicted_magnitude(g, k, earth_dist_au, sun_dist_au) -> float` (inchangé)
  - `sources.comets.comet_objects(comets: pd.DataFrame) -> tuple[list[ObjectRow], list[CometElements]]`
- Consumes: `sources.comets.load_comets` (existant), fixtures `kernel_path` / `fallback_comets_path` (existantes).

- [ ] **Step 1: Écrire le test du modèle + writer (échoue)**

Create `oracle/tests/test_records.py`:

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.records import CometElements, EphemRow, FixedRow, ObjectRow


def _meta() -> BuildMeta:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now,
        mpc_epoch=None,
        window_start=now,
        window_end=now,
        skyfield_kernel="de421.bsp",
    )


def test_schema_version_is_2() -> None:
    assert SCHEMA_VERSION == 2


def test_unified_writer_populates_all_tables(tmp_path: Path) -> None:
    objects = [
        ObjectRow("NGC1976", "dso", "Orion Nebula", "NGC1976"),
        ObjectRow("star:HIP32349", "star", "Sirius", "HR 2491"),
        ObjectRow("planet:mars", "planet", "Mars", None),
        ObjectRow("moon", "moon", "Moon", None),
        ObjectRow("C/2023 A3", "comet", "Tsuchinshan-ATLAS", "C/2023 A3"),
    ]
    fixed = [
        FixedRow("NGC1976", 83.8, -5.4, 4.0, "nebula", 85.0, "Ori", "M42", "NGC1976"),
        FixedRow("star:HIP32349", 101.3, -16.7, -1.46, "star", None, "CMa", None, None),
    ]
    ephem = [
        EphemRow("planet:mars", "2026-08-01T00:00:00Z", 120.0, 20.0, 1.5, 1.6, -1.0, None, "Leo"),
        EphemRow("moon", "2026-08-01T00:00:00Z", 200.0, -10.0, 0.0026, 1.0, None, 0.42, "Vir"),
        EphemRow("C/2023 A3", "2026-08-01T00:00:00Z", 45.0, 15.0, 1.2, 0.9, 8.5, None, "Ari"),
    ]
    elements = [
        CometElements("C/2023 A3", 2460000.5, 0.39, 1.0001, 139.1, 308.5, 21.6, 5.0, 4.0),
    ]

    out = build_reference_db(tmp_path / "reference.sqlite", objects, fixed, ephem, elements, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == 2
        assert con.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 5
        assert con.execute("SELECT COUNT(*) FROM fixed_object").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()[0] == 1
        # FK integrity: every child row references an existing object
        for child, col in (("fixed_object", "object_id"), ("ephemeris", "object_id"), ("comet_elements", "object_id")):
            (orphans,) = con.execute(
                f"SELECT COUNT(*) FROM {child} c "
                f"LEFT JOIN objects o ON c.{col} = o.id WHERE o.id IS NULL"
            ).fetchone()
            assert orphans == 0, child
        # illumination present for the Moon, NULL for the comet
        (illum_moon,) = con.execute(
            "SELECT illumination FROM ephemeris WHERE object_id='moon'"
        ).fetchone()
        assert illum_moon == 0.42
        (illum_comet,) = con.execute(
            "SELECT illumination FROM ephemeris WHERE object_id='C/2023 A3'"
        ).fetchone()
        assert illum_comet is None
    finally:
        con.close()
```

- [ ] **Step 2: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_records.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.records'`.

- [ ] **Step 3: Créer le modèle de données `records.py`**

Create `oracle/oracle/records.py`:

```python
"""Unified output model for the reference.sqlite v2 artifact.

One dataclass per target table. Every writer input and every compute/source
output is expressed with these types, so the schema has a single source of
truth on the Python side too.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectRow:
    """Identity row, common to every catalogue object (table ``objects``)."""

    id: str  # stable id: packed MPC / "planet:mars" / "moon" / "NGC1976" / "star:HIP32349"
    kind: str  # comet | planet | moon | sun | dso | star
    name: str | None
    designation: str | None


@dataclass(frozen=True)
class FixedRow:
    """Static position + attributes for a fixed object (table ``fixed_object``)."""

    object_id: str
    ra_deg: float  # of-date JNow at generation time
    dec_deg: float
    apparent_mag: float | None
    object_type: str | None  # galaxy / nebula / cluster / double-star / star / ...
    size_arcmin: float | None
    constellation: str | None
    messier: str | None  # "M42" if applicable
    ngc_ic: str | None  # "NGC1976" / "IC434"


@dataclass(frozen=True)
class EphemRow:
    """One daily apparent-position sample for an ephemeral object (table ``ephemeris``)."""

    object_id: str
    sample_utc: str  # ISO-8601 UTC, "Z" suffix
    ra_deg: float  # of-date JNow
    dec_deg: float
    earth_dist_au: float | None
    sun_dist_au: float | None
    apparent_mag: float | None  # reliable for planets/luminaries; estimate for comets
    illumination: float | None  # illuminated fraction 0..1 (Moon/Venus/Mercury); NULL otherwise
    constellation: str | None


@dataclass(frozen=True)
class CometElements:
    """Comet-specific orbital elements (table ``comet_elements``)."""

    object_id: str
    epoch_jd: float | None
    perihelion_q_au: float
    eccentricity: float
    inclination_deg: float
    arg_perihelion_deg: float
    node_deg: float
    # mag_h/mag_k = comet total-magnitude params (g, k),
    # m = g + 5*log10(delta) + 2.5*k*log10(r); NOT the asteroid H,G system.
    mag_h: float | None
    mag_k: float | None
```

- [ ] **Step 4: Réécrire `schema.sql` en v2**

Replace the entire contents of `oracle/schema.sql`:

```sql
-- oracle/schema.sql  (the contract; meta.schema_version gates compatibility)
-- schema_version = 2 : base catalogue commune (all object families, one artifact)

CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,   -- 2 ; a consumer refuses a version it does not know
  generated_at     TEXT    NOT NULL,   -- ISO-8601 UTC
  mpc_epoch        TEXT,               -- MPC elements epoch (comets)
  window_start     TEXT    NOT NULL,   -- ephemeris window start (UTC)
  window_end       TEXT    NOT NULL,   -- ephemeris window end (UTC) ; ~60 rolling days
  skyfield_kernel  TEXT                -- "de421.bsp"
);

-- identity, common to EVERY catalogue object
CREATE TABLE objects (
  id           TEXT PRIMARY KEY,       -- stable id (packed MPC / "planet:mars" /
                                       --  "moon" / "sun" / "NGC1976" / "star:HIP32349")
  kind         TEXT NOT NULL,          -- comet | planet | moon | sun | dso | star
  name         TEXT,                   -- common name (nullable)
  designation  TEXT                    -- catalogue designation (nullable)
);

-- fixed objects: one position + static attributes (deep-sky AND stars)
CREATE TABLE fixed_object (
  object_id     TEXT PRIMARY KEY REFERENCES objects(id),
  ra_deg        REAL NOT NULL,         -- of-date JNow at generation
  dec_deg       REAL NOT NULL,
  apparent_mag  REAL,
  object_type   TEXT,                  -- galaxy / nebula / cluster / double-star / star / ...
  size_arcmin   REAL,                  -- apparent size (nullable, e.g. stars)
  constellation TEXT,
  messier       TEXT,                  -- "M42" if applicable (nullable)
  ngc_ic        TEXT                   -- "NGC1976" / "IC434" (nullable)
);

-- ephemeral objects: precomputed samples (comets + planets + Moon + Sun)
CREATE TABLE ephemeris (
  object_id     TEXT NOT NULL REFERENCES objects(id),
  sample_utc    TEXT NOT NULL,         -- daily step across the window
  ra_deg        REAL NOT NULL,         -- of-date JNow
  dec_deg       REAL NOT NULL,
  earth_dist_au REAL,                  -- distance to Earth (nullable)
  sun_dist_au   REAL,                  -- distance to Sun (nullable: the Sun has none)
  apparent_mag  REAL,                  -- reliable planets/luminaries; estimate for comets
  illumination  REAL,                  -- illuminated fraction 0..1 (Moon/Venus/Mercury); NULL otherwise
  constellation TEXT,
  PRIMARY KEY (object_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);

-- comet-specific extras (orbital elements)
CREATE TABLE comet_elements (
  object_id          TEXT PRIMARY KEY REFERENCES objects(id),
  epoch_jd           REAL,
  perihelion_q_au    REAL NOT NULL,
  eccentricity       REAL NOT NULL,
  inclination_deg    REAL NOT NULL,
  arg_perihelion_deg REAL NOT NULL,
  node_deg           REAL NOT NULL,
  -- mag_h/mag_k hold the comet total-magnitude params g,k
  -- (m = g + 5*log10(delta) + 2.5*k*log10(r)); NOT the asteroid H,G system.
  mag_h              REAL,
  mag_k              REAL
);
```

- [ ] **Step 5: Réécrire `build_db.py` en writer unifié**

Replace the entire contents of `oracle/oracle/build_db.py`:

```python
"""Build the reference.sqlite v2 artifact from the unified record model."""

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

import oracle
from oracle.records import CometElements, EphemRow, FixedRow, ObjectRow

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class BuildMeta:
    """Provenance metadata stored in the ``meta`` table of the artifact."""

    schema_version: int
    generated_at: str
    mpc_epoch: str | None
    window_start: str
    window_end: str
    skyfield_kernel: str


def _schema_sql() -> str:
    """Return the DDL from ``oracle/schema.sql`` (one level above the package)."""
    return (Path(oracle.__file__).resolve().parent.parent / "schema.sql").read_text()


def _opt(row: pd.Series, key: str) -> float | None:
    """Return ``row[key]`` as a float, or ``None`` when missing/NaN."""
    value = row.get(key)
    return float(value) if pd.notna(value) else None


def build_reference_db(
    out_path: Path,
    objects: list[ObjectRow],
    fixed: list[FixedRow],
    ephem: list[EphemRow],
    comet_elements: list[CometElements],
    meta: BuildMeta,
) -> Path:
    """Write the full unified catalogue into a fresh ``reference.sqlite`` at ``out_path``."""
    if out_path.exists():
        out_path.unlink()
    con = sqlite3.connect(out_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(_schema_sql())
        con.execute(
            "INSERT INTO meta (schema_version, generated_at, mpc_epoch, "
            "window_start, window_end, skyfield_kernel) VALUES "
            "(:schema_version, :generated_at, :mpc_epoch, :window_start, "
            ":window_end, :skyfield_kernel)",
            asdict(meta),
        )
        con.executemany(
            "INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)",
            [(o.id, o.kind, o.name, o.designation) for o in objects],
        )
        con.executemany(
            "INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag, "
            "object_type, size_arcmin, constellation, messier, ngc_ic) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    f.object_id, f.ra_deg, f.dec_deg, f.apparent_mag, f.object_type,
                    f.size_arcmin, f.constellation, f.messier, f.ngc_ic,
                )
                for f in fixed
            ],
        )
        con.executemany(
            "INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg, "
            "earth_dist_au, sun_dist_au, apparent_mag, illumination, constellation) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    r.object_id, r.sample_utc, r.ra_deg, r.dec_deg, r.earth_dist_au,
                    r.sun_dist_au, r.apparent_mag, r.illumination, r.constellation,
                )
                for r in ephem
            ],
        )
        con.executemany(
            "INSERT INTO comet_elements (object_id, epoch_jd, perihelion_q_au, "
            "eccentricity, inclination_deg, arg_perihelion_deg, node_deg, mag_h, mag_k) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    c.object_id, c.epoch_jd, c.perihelion_q_au, c.eccentricity,
                    c.inclination_deg, c.arg_perihelion_deg, c.node_deg, c.mag_h, c.mag_k,
                )
                for c in comet_elements
            ],
        )
        con.commit()
    finally:
        con.close()
    return out_path
```

- [ ] **Step 6: Mettre à jour le compute comète (`ephemeris.py`) pour la nouvelle `EphemRow`**

In `oracle/oracle/compute/ephemeris.py`, remove the local `EphemRow` dataclass definition (lines defining `@dataclass(frozen=True) class EphemRow: ...`) and import it from `records` instead. Replace the imports block and the row construction. The full file becomes:

```python
"""Compute daily apparent (of-date) comet ephemeris with skyfield."""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from skyfield.api import Loader, load_constellation_map, position_of_radec
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc

from oracle.records import EphemRow

__all__ = ["EphemRow", "predicted_magnitude", "compute_ephemeris"]


def predicted_magnitude(
    g: float, k: float, earth_dist_au: float, sun_dist_au: float
) -> float:
    """Total comet magnitude: m = g + 5*log10(delta) + 2.5*k*log10(r)."""
    return g + 5.0 * math.log10(earth_dist_au) + 2.5 * k * math.log10(sun_dist_au)


def compute_ephemeris(
    comets: pd.DataFrame,
    kernel_path: Path,
    start_utc: datetime,
    days: int = 60,
) -> list[EphemRow]:
    """Daily apparent RA/Dec (of-date) for each comet over ``days`` days."""
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    else:
        start_utc = start_utc.astimezone(timezone.utc)

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    sun, earth = eph["sun"], eph["earth"]
    constellation_at = load_constellation_map()

    rows: list[EphemRow] = []
    for designation, row in comets.iterrows():
        comet = sun + mpc.comet_orbit(row, ts, GM_SUN)
        g = row.get("magnitude_g")
        k = row.get("magnitude_k")
        for day in range(days):
            when = start_utc + timedelta(days=day)
            t = ts.from_datetime(when)
            astrometric = earth.at(t).observe(comet)
            ra, dec, delta = astrometric.apparent().radec(epoch="date")
            r = sun.at(t).observe(comet).distance()
            mag = (
                predicted_magnitude(float(g), float(k), delta.au, r.au)
                if pd.notna(g) and pd.notna(k)
                else None
            )
            try:
                const = constellation_at(position_of_radec(ra.hours, dec.degrees))
            except Exception:
                const = None
            rows.append(
                EphemRow(
                    object_id=str(designation),
                    sample_utc=when.isoformat().replace("+00:00", "Z"),
                    ra_deg=ra.degrees % 360.0,
                    dec_deg=dec.degrees,
                    earth_dist_au=delta.au,
                    sun_dist_au=r.au,
                    apparent_mag=mag,
                    illumination=None,
                    constellation=const,
                )
            )
    return rows
```

- [ ] **Step 7: Ajouter l'adaptateur `comet_objects` dans `sources/comets.py`**

Add to `oracle/oracle/sources/comets.py`. First extend the imports at the top (after `import pandas as pd`):

```python
from oracle.build_db import _opt
from oracle.records import CometElements, ObjectRow
```

Then append this function at the end of the file:

```python
def comet_objects(comets: pd.DataFrame) -> tuple[list[ObjectRow], list[CometElements]]:
    """Split a comet DataFrame into identity rows + orbital-element rows.

    The id is the MPC designation (also used as the ephemeris ``object_id``),
    so ephemeris FK integrity holds against ``objects``.
    """
    objs: list[ObjectRow] = []
    elems: list[CometElements] = []
    for designation, row in comets.iterrows():
        oid = str(designation)
        name = str(row["name"]) if pd.notna(row.get("name")) else None
        objs.append(
            ObjectRow(
                id=oid,
                kind="comet",
                name=name,
                designation=str(row.get("designation", designation)),
            )
        )
        elems.append(
            CometElements(
                object_id=oid,
                epoch_jd=_opt(row, "epoch_jd"),
                perihelion_q_au=float(row["perihelion_distance_au"]),
                eccentricity=float(row["eccentricity"]),
                inclination_deg=float(row["inclination_degrees"]),
                arg_perihelion_deg=float(row["argument_of_perihelion_degrees"]),
                node_deg=float(row["longitude_of_ascending_node_degrees"]),
                mag_h=_opt(row, "magnitude_g"),
                mag_k=_opt(row, "magnitude_k"),
            )
        )
    return objs, elems
```

- [ ] **Step 8: Mettre à jour les tests comètes existants pour le nouveau modèle**

In `oracle/tests/test_ephemeris.py`, update the field names that changed (`comet_id` → `object_id`, `predicted_mag` → `apparent_mag`). Replace:
- line `assert r.comet_id in set(comets.index)` → `assert r.object_id in set(comets.index)`
- the last test body `assert rows[0].predicted_mag is None` → `assert rows[0].apparent_mag is None`

Rewrite `oracle/tests/test_build_db.py` entirely (the old `comets`/`comet_ephemeris` tables no longer exist):

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.sources.comets import comet_objects, load_comets


def _meta() -> BuildMeta:
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now,
        mpc_epoch=None,
        window_start=now,
        window_end=now,
        skyfield_kernel="de421.bsp",
    )


def test_build_db_comets_are_queryable(tmp_path: Path, kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=4)
    objects, elements = comet_objects(comets)

    out = build_reference_db(tmp_path / "reference.sqlite", objects, [], rows, elements, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == SCHEMA_VERSION
        (n_obj,) = con.execute("SELECT COUNT(*) FROM objects WHERE kind='comet'").fetchone()
        assert n_obj == 3
        (n_elem,) = con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()
        assert n_elem == 3
        (n_ephem,) = con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()
        assert n_ephem == 12  # 3 comets x 4 samples
        (orphans,) = con.execute(
            "SELECT COUNT(*) FROM ephemeris e "
            "LEFT JOIN objects o ON e.object_id = o.id WHERE o.id IS NULL"
        ).fetchone()
        assert orphans == 0
    finally:
        con.close()
```

- [ ] **Step 9: Lancer les tests de la tâche — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_records.py tests/test_build_db.py tests/test_ephemeris.py -v`
Expected: PASS (all). `test_build_pipeline.py` échouera encore (build.py pas mis à jour) — c'est attendu, il est traité en Task 7.

- [ ] **Step 10: Commit**

```bash
git add oracle/oracle/records.py oracle/schema.sql oracle/oracle/build_db.py \
        oracle/oracle/compute/ephemeris.py oracle/oracle/sources/comets.py \
        oracle/tests/test_records.py oracle/tests/test_build_db.py oracle/tests/test_ephemeris.py
git commit -m "feat(oracle): unified v2 record model + schema + writer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Helper fetch+fallback partagé + refactor `comets.py`

Extrait le patron « fetch réseau, retombe sur snapshot bundlé » en une seule fonction réutilisée par toutes les sources fetchables, et refactore `fetch_comet_els` pour l'utiliser (une seule source de vérité du patron). Les tâches deep-sky/étoiles en dépendent.

**Files:**
- Create: `oracle/oracle/sources/_fetch.py`
- Modify: `oracle/oracle/sources/comets.py` (`fetch_comet_els` devient un wrapper)
- Test: `oracle/tests/test_fetch.py` (create)

**Interfaces:**
- Produces:
  - `sources._fetch.fetch_with_fallback(dest: Path, url: str, fallback_name: str, *, opener: Callable[[str], object] = urllib.request.urlopen) -> Path` — écrit `url` dans `dest` ; sur toute exception (ou corps vide), copie `oracle.data_dir() / fallback_name` dans `dest`. Retourne `dest`.
- Consumes: `oracle.data_dir()` (existant).
- Preserves: `sources.comets.fetch_comet_els(dest, url=COMET_ELS_URL, *, opener=...) -> Path` (signature inchangée, comportement identique).

- [ ] **Step 1: Écrire le test du helper (échoue)**

Create `oracle/tests/test_fetch.py`:

```python
from pathlib import Path

import oracle
from oracle.sources._fetch import fetch_with_fallback


def test_fetch_writes_body_on_success(tmp_path: Path) -> None:
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"fresh-body"

    dest = tmp_path / "out.txt"
    result = fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=lambda url: _Resp())
    assert result == dest
    assert dest.read_bytes() == b"fresh-body"


def test_fetch_falls_back_on_error(tmp_path: Path) -> None:
    def _boom(url):
        raise OSError("network down")

    dest = tmp_path / "out.txt"
    fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=_boom)
    # dest must equal the bundled fallback byte-for-byte
    assert dest.read_bytes() == (oracle.data_dir() / "CometEls.fallback.txt").read_bytes()


def test_fetch_falls_back_on_empty_body(tmp_path: Path) -> None:
    class _Empty:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b""

    dest = tmp_path / "out.txt"
    fetch_with_fallback(dest, "https://example/x", "CometEls.fallback.txt", opener=lambda url: _Empty())
    assert dest.read_bytes() == (oracle.data_dir() / "CometEls.fallback.txt").read_bytes()
```

- [ ] **Step 2: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.sources._fetch'`.

- [ ] **Step 3: Implémenter `_fetch.py`**

Create `oracle/oracle/sources/_fetch.py`:

```python
"""Shared fetch-with-fallback helper for reference data sources.

A build must never fail because a source is unreachable: on any error (or an
empty response), the bundled snapshot named ``fallback_name`` under
``oracle.data_dir()`` is copied in place.
"""

import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

import oracle

logger = logging.getLogger(__name__)


def fetch_with_fallback(
    dest: Path,
    url: str,
    fallback_name: str,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch ``url`` to ``dest``; on failure copy the bundled ``fallback_name``."""
    try:
        with opener(url) as response:  # type: ignore[attr-defined]
            body = response.read()
        if not body:
            raise OSError("empty response body")
        dest.write_bytes(body)
    except Exception as exc:
        logger.warning(
            "%s fetch failed, using bundled fallback %s: %s", url, fallback_name, exc
        )
        shutil.copyfile(oracle.data_dir() / fallback_name, dest)
    return dest
```

- [ ] **Step 4: Refactorer `fetch_comet_els` en wrapper**

In `oracle/oracle/sources/comets.py`, replace the top-of-file imports block:

```python
import logging
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc

import oracle

logger = logging.getLogger(__name__)
```

with (keep the `_opt` / `CometElements` / `ObjectRow` imports added in Task 1):

```python
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc

from oracle.build_db import _opt
from oracle.records import CometElements, ObjectRow
from oracle.sources._fetch import fetch_with_fallback
```

Then replace the whole `fetch_comet_els` function body with the wrapper:

```python
def fetch_comet_els(
    dest: Path,
    url: str = COMET_ELS_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh comet elements to ``dest``; fall back to the bundled snapshot."""
    return fetch_with_fallback(dest, url, "CometEls.fallback.txt", opener=opener)
```

(The `import oracle`, `import logging`, `import shutil`, and `logger` are no longer used in `comets.py` — remove them.)

- [ ] **Step 5: Lancer les tests helper + comètes — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_fetch.py tests/test_comets_fetch.py tests/test_comets_load.py -v`
Expected: PASS. `test_comets_fetch.py` (comportement fallback existant) doit rester vert : le wrapper préserve le comportement octet-pour-octet.

- [ ] **Step 6: Commit**

```bash
git add oracle/oracle/sources/_fetch.py oracle/oracle/sources/comets.py oracle/tests/test_fetch.py
git commit -m "refactor(oracle): shared fetch-with-fallback helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Source deep-sky (OpenNGC — Messier + NGC/IC)

Ajoute la source deep-sky : fetch OpenNGC (CSV `;`-séparé) + fallback bundlé + parser vers `DeepSkyRecord` (J2000, avant projection). Une seule source couvre Messier (via la colonne de cross-référence `M`) *et* NGC/IC.

**Files:**
- Create: `oracle/oracle/sources/deep_sky.py`
- Create: `oracle/data/OpenNGC.fallback.csv` (snapshot committé)
- Test: `oracle/tests/test_deep_sky.py`
- Modify: `oracle/tests/conftest.py` (ajout fixture `fallback_open_ngc_path`)

**Interfaces:**
- Produces:
  - `sources.deep_sky.OpenNgcRecord(id: str, name: str | None, designation: str, object_type: str, ra_deg_j2000: float, dec_deg_j2000: float, apparent_mag: float | None, size_arcmin: float | None, constellation: str | None, messier: str | None, ngc_ic: str)`
  - `sources.deep_sky.load_deep_sky(path: Path) -> list[OpenNgcRecord]`
  - `sources.deep_sky.fetch_open_ngc(dest: Path, url: str = OPEN_NGC_URL, *, opener=urllib.request.urlopen) -> Path`
  - `sources.deep_sky.OPEN_NGC_URL: str`
- Consumes: `oracle.data_dir()` (existant).

- [ ] **Step 1: Committer le snapshot fallback OpenNGC**

Download the real OpenNGC catalogue and commit it as the offline fallback / test fixture:

```bash
curl -fsSL https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv \
     -o oracle/data/OpenNGC.fallback.csv
head -1 oracle/data/OpenNGC.fallback.csv   # sanity: expect the ';'-separated header
git add oracle/data/OpenNGC.fallback.csv
git commit -m "data(oracle): bundle OpenNGC snapshot as deep-sky fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Header must be exactly:
`Name;Type;RA;Dec;Const;MajAx;MinAx;PosAng;B-Mag;V-Mag;J-Mag;H-Mag;K-Mag;SurfBr;Hubble;Pax;Pm-RA;Pm-Dec;RadVel;Redshift;Cstar U-Mag;Cstar B-Mag;Cstar V-Mag;M;NGC;IC;Cstar Names;Identifiers;Common names;NED notes;OpenNGC notes;Sources`

- [ ] **Step 2: Ajouter la fixture + écrire le test (échoue)**

In `oracle/tests/conftest.py`, append:

```python
@pytest.fixture
def fallback_open_ngc_path() -> Path:
    return oracle.data_dir() / "OpenNGC.fallback.csv"
```

Create `oracle/tests/test_deep_sky.py`:

```python
from oracle.sources.deep_sky import load_deep_sky


def test_load_deep_sky_parses_and_ranges(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    assert len(records) > 10000  # OpenNGC ships ~13k physical objects
    for r in records[:200]:
        assert 0.0 <= r.ra_deg_j2000 < 360.0
        assert -90.0 <= r.dec_deg_j2000 <= 90.0
        assert r.ngc_ic  # every deep-sky object carries an NGC/IC-style designation


def test_deep_sky_covers_all_110_messier(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    messier = {r.messier for r in records if r.messier}
    assert len(messier) == 110  # M1..M110, all present exactly once as a set


def test_deep_sky_m42_is_the_orion_nebula(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    m42 = next(r for r in records if r.messier == "M42")
    assert m42.ngc_ic == "NGC1976"
    assert m42.object_type == "nebula"
    assert m42.constellation == "Ori"
    # of-date projection happens later; here RA/Dec are raw J2000
    assert 83.0 < m42.ra_deg_j2000 < 84.5
    assert -6.0 < m42.dec_deg_j2000 < -5.0


def test_deep_sky_skips_non_physical_types(fallback_open_ngc_path) -> None:
    records = load_deep_sky(fallback_open_ngc_path)
    types = {r.object_type for r in records}
    # Dup / NonEx / Other are dropped, so no record maps to them
    assert None not in types
```

- [ ] **Step 3: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_deep_sky.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.sources.deep_sky'`.

- [ ] **Step 4: Implémenter `deep_sky.py`**

Create `oracle/oracle/sources/deep_sky.py`:

```python
"""Load deep-sky objects (Messier + NGC/IC) from an OpenNGC CSV file."""

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from oracle.sources._fetch import fetch_with_fallback

OPEN_NGC_URL = (
    "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv"
)

# OpenNGC Type codes → coarse object_type used by the catalogue.
_TYPE_MAP = {
    "G": "galaxy", "GPair": "galaxy", "GTrpl": "galaxy", "GGroup": "galaxy",
    "PN": "nebula", "HII": "nebula", "EmN": "nebula", "RfN": "nebula",
    "Neb": "nebula", "SNR": "nebula", "DrkN": "nebula",
    "Cl+N": "cluster", "OCl": "cluster", "GCl": "cluster", "*Ass": "cluster",
    "*": "star", "**": "double-star",
}
# Non-physical / bookkeeping rows we never expose.
_SKIP_TYPES = {"Dup", "NonEx", "Other"}

_DESIG = re.compile(r"([A-Za-z]+)0*(\d.*)")


@dataclass(frozen=True)
class OpenNgcRecord:
    """One deep-sky object, J2000 (position projected to of-date later)."""

    id: str
    name: str | None
    designation: str
    object_type: str
    ra_deg_j2000: float
    dec_deg_j2000: float
    apparent_mag: float | None
    size_arcmin: float | None
    constellation: str | None
    messier: str | None
    ngc_ic: str


def _normalize_designation(name: str) -> str:
    """"NGC0224" -> "NGC224", "IC0434" -> "IC434", "Mel022" -> "Mel22"."""
    m = _DESIG.match(name)
    return f"{m.group(1)}{m.group(2)}" if m else name


def _hms_to_deg(value: str) -> float:
    """Sexagesimal RA "HH:MM:SS.SS" -> degrees."""
    h, m, s = value.split(":")
    return (int(h) + int(m) / 60.0 + float(s) / 3600.0) * 15.0


def _dms_to_deg(value: str) -> float:
    """Sexagesimal Dec "+DD:MM:SS.S" -> degrees."""
    sign = -1.0 if value.strip().startswith("-") else 1.0
    d, m, s = value.replace("+", "").replace("-", "").split(":")
    return sign * (int(d) + int(m) / 60.0 + float(s) / 3600.0)


def _float_or_none(value: object) -> float | None:
    return float(value) if pd.notna(value) and str(value).strip() != "" else None


def load_deep_sky(path: Path) -> list[OpenNgcRecord]:
    """Parse an OpenNGC CSV into deep-sky records (J2000, non-physical rows dropped)."""
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)
    records: list[OpenNgcRecord] = []
    for _, row in df.iterrows():
        type_code = row["Type"].strip()
        if type_code in _SKIP_TYPES:
            continue
        object_type = _TYPE_MAP.get(type_code)
        if object_type is None:
            continue
        ra_raw, dec_raw = row["RA"].strip(), row["Dec"].strip()
        if not ra_raw or not dec_raw:
            continue  # rows without a position are not usable targets
        designation = _normalize_designation(row["Name"].strip())
        messier = f"M{int(row['M'])}" if row["M"].strip() else None
        common = row["Common names"].strip()
        name = common.split(",")[0] if common else None
        v_mag = _float_or_none(row["V-Mag"])
        b_mag = _float_or_none(row["B-Mag"])
        records.append(
            OpenNgcRecord(
                id=designation,
                name=name,
                designation=designation,
                object_type=object_type,
                ra_deg_j2000=_hms_to_deg(ra_raw),
                dec_deg_j2000=_dms_to_deg(dec_raw),
                apparent_mag=v_mag if v_mag is not None else b_mag,
                size_arcmin=_float_or_none(row["MajAx"]),
                constellation=row["Const"].strip() or None,
                messier=messier,
                ngc_ic=designation,
            )
        )
    return records


def fetch_open_ngc(
    dest: Path,
    url: str = OPEN_NGC_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh OpenNGC to ``dest``; fall back to the bundled snapshot on failure."""
    return fetch_with_fallback(dest, url, "OpenNGC.fallback.csv", opener=opener)
```

- [ ] **Step 5: Lancer le test — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_deep_sky.py -v`
Expected: PASS. If `test_deep_sky_covers_all_110_messier` reports a count ≠ 110, inspect with `python -c "from oracle.sources.deep_sky import load_deep_sky; import oracle; rs=load_deep_sky(oracle.data_dir()/'OpenNGC.fallback.csv'); ms=sorted({r.messier for r in rs if r.messier}); print(len(ms)); print([f'M{n}' for n in range(1,111) if f'M{n}' not in ms])"` and confirm the `M` column formatting; do not weaken the assertion.

- [ ] **Step 6: Commit**

```bash
git add oracle/oracle/sources/deep_sky.py oracle/tests/test_deep_sky.py oracle/tests/conftest.py
git commit -m "feat(oracle): OpenNGC deep-sky source (Messier + NGC/IC)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Source étoiles nommées (IAU-CSN)

Ajoute la source étoiles : fetch IAU-CSN (`IAU-CSN.txt`, texte aligné) + fallback bundlé + parser vers `StarRecord` (J2000 décimal, avant projection).

**Files:**
- Create: `oracle/oracle/sources/stars.py`
- Create: `oracle/data/IAU-CSN.fallback.txt` (snapshot committé)
- Test: `oracle/tests/test_stars.py`
- Modify: `oracle/tests/conftest.py` (ajout fixture `fallback_iau_csn_path`)

**Interfaces:**
- Produces:
  - `sources.stars.StarRecord(id: str, name: str, designation: str | None, ra_deg_j2000: float, dec_deg_j2000: float, apparent_mag: float | None, constellation: str | None)`
  - `sources.stars.load_stars(path: Path) -> list[StarRecord]`
  - `sources.stars.fetch_iau_csn(dest: Path, url: str = IAU_CSN_URL, *, opener=urllib.request.urlopen) -> Path`
  - `sources.stars.IAU_CSN_URL: str`
- Consumes: `oracle.data_dir()`.

- [ ] **Step 1: Committer le snapshot fallback IAU-CSN**

```bash
curl -fsSL https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt \
     -o oracle/data/IAU-CSN.fallback.txt
grep -c '^[^#]' oracle/data/IAU-CSN.fallback.txt   # sanity: > 400 named stars
git add oracle/data/IAU-CSN.fallback.txt
git commit -m "data(oracle): bundle IAU-CSN snapshot as named-star fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

The file's data rows are whitespace-aligned with these trailing columns (fixed order, one token each): `... Con # WDS_J mag bnd HIP HD RA(J2000) Dec(J2000) Date [Notes]`. RA/Dec are **decimal degrees, J2000**. Comment lines start with `#`.

- [ ] **Step 2: Ajouter la fixture + écrire le test (échoue)**

In `oracle/tests/conftest.py`, append:

```python
@pytest.fixture
def fallback_iau_csn_path() -> Path:
    return oracle.data_dir() / "IAU-CSN.fallback.txt"
```

Create `oracle/tests/test_stars.py`:

```python
from oracle.sources.stars import load_stars


def test_load_stars_parses_and_ranges(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    assert len(stars) > 400  # IAU-CSN lists 450+ approved names
    for s in stars:
        assert 0.0 <= s.ra_deg_j2000 < 360.0
        assert -90.0 <= s.dec_deg_j2000 <= 90.0
        assert s.name
        assert s.id.startswith("star:")


def test_stars_include_sirius(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    sirius = next(s for s in stars if s.name == "Sirius")
    assert sirius.constellation == "CMa"
    assert sirius.apparent_mag is not None and sirius.apparent_mag < 0.0  # ~ -1.46
    assert 100.0 < sirius.ra_deg_j2000 < 102.0  # ~101.29 deg
    assert -17.5 < sirius.dec_deg_j2000 < -16.0  # ~ -16.72 deg


def test_stars_acamar_row_parses(fallback_iau_csn_path) -> None:
    stars = load_stars(fallback_iau_csn_path)
    acamar = next(s for s in stars if s.name == "Acamar")
    assert acamar.constellation == "Eri"
    assert 44.0 < acamar.ra_deg_j2000 < 45.0  # ~44.565 deg
```

- [ ] **Step 3: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_stars.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.sources.stars'`.

- [ ] **Step 4: Implémenter `stars.py`**

The parser anchors on the `Date` column (a `YYYY-MM-DD` token) to locate the fixed-order trailing columns from the right, so the variable-length name/designation prefix is irrelevant to field alignment. `Name/ASCII` is the first token; `_` means "missing".

Create `oracle/oracle/sources/stars.py`:

```python
"""Load named stars from an IAU Catalog of Star Names (IAU-CSN.txt) file."""

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from oracle.sources._fetch import fetch_with_fallback

IAU_CSN_URL = "https://www.pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt"

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class StarRecord:
    """One IAU-named star, J2000 (position projected to of-date later)."""

    id: str
    name: str
    designation: str | None
    ra_deg_j2000: float
    dec_deg_j2000: float
    apparent_mag: float | None
    constellation: str | None


def _tok_or_none(token: str) -> str | None:
    return None if token == "_" else token


def _float_or_none(token: str) -> float | None:
    return None if token == "_" else float(token)


def load_stars(path: Path) -> list[StarRecord]:
    """Parse an IAU-CSN.txt file into star records (J2000 decimal degrees).

    Columns are whitespace-aligned; the trailing block is fixed-order and
    one token each: ``... Con # WDS_J mag bnd HIP HD RA Dec Date [Notes]``.
    We find the Date token and index the rest relative to it.
    """
    stars: list[StarRecord] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        toks = line.split()
        date_idx = next((i for i, t in enumerate(toks) if _DATE.match(t)), None)
        if date_idx is None or date_idx < 9:
            continue  # malformed / non-data line
        ra = _float_or_none(toks[date_idx - 2])
        dec = _float_or_none(toks[date_idx - 1])
        if ra is None or dec is None:
            continue
        name = toks[0]
        hip = _tok_or_none(toks[date_idx - 4])
        mag = _float_or_none(toks[date_idx - 6])
        con = _tok_or_none(toks[date_idx - 9])
        star_id = f"star:HIP{hip}" if hip is not None else f"star:{name}"
        stars.append(
            StarRecord(
                id=star_id,
                name=name,
                designation=f"HIP {hip}" if hip is not None else None,
                ra_deg_j2000=ra % 360.0,
                dec_deg_j2000=dec,
                apparent_mag=mag,
                constellation=con,
            )
        )
    return stars


def fetch_iau_csn(
    dest: Path,
    url: str = IAU_CSN_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh IAU-CSN to ``dest``; fall back to the bundled snapshot on failure."""
    return fetch_with_fallback(dest, url, "IAU-CSN.fallback.txt", opener=opener)
```

- [ ] **Step 5: Lancer le test — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_stars.py -v`
Expected: PASS. If a specific star fails to parse, inspect the raw line with `grep '^Sirius' oracle/data/IAU-CSN.fallback.txt` and confirm the trailing-column order; the anchor logic depends only on the Date token position.

- [ ] **Step 6: Commit**

```bash
git add oracle/oracle/sources/stars.py oracle/tests/test_stars.py oracle/tests/conftest.py
git commit -m "feat(oracle): IAU-CSN named-star source

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Projection J2000 → of-date pour les objets fixes

Ajoute la projection des positions fixes (deep-sky + étoiles) de J2000 vers l'apparent of-date (JNow) à l'instant de génération, via skyfield `Star`. Vectorisé (un seul instant, N objets).

**Files:**
- Create: `oracle/oracle/compute/fixed.py`
- Test: `oracle/tests/test_fixed.py`

**Interfaces:**
- Produces:
  - `compute.fixed.project_to_of_date(points: list[tuple[str, float, float]], kernel_path: Path, when_utc: datetime) -> dict[str, tuple[float, float]]` — mappe `id → (ra_deg_ofdate, dec_deg_ofdate)`. Chaque `point` est `(id, ra_deg_j2000, dec_deg_j2000)`.
- Consumes: kernel `de421.bsp`.

- [ ] **Step 1: Écrire le test (échoue)**

Create `oracle/tests/test_fixed.py`:

```python
import math
from datetime import datetime, timezone

from skyfield.api import Loader, Star

from oracle.compute.fixed import project_to_of_date


def test_project_shape_and_ranges(kernel_path) -> None:
    points = [
        ("NGC1976", 83.82, -5.39),   # M42, J2000
        ("star:HIP32349", 101.29, -16.72),  # Sirius, J2000
    ]
    when = datetime(2026, 8, 1, tzinfo=timezone.utc)
    out = project_to_of_date(points, kernel_path, when)
    assert set(out) == {"NGC1976", "star:HIP32349"}
    for ra, dec in out.values():
        assert 0.0 <= ra < 360.0
        assert -90.0 <= dec <= 90.0


def test_project_is_of_date_not_j2000(kernel_path) -> None:
    # of-date must measurably differ from the input J2000 (precession + aberration).
    points = [("NGC1976", 83.82, -5.39)]
    when = datetime(2026, 8, 1, tzinfo=timezone.utc)
    ra_ofdate, _ = project_to_of_date(points, kernel_path, when)["NGC1976"]
    assert abs(ra_ofdate - 83.82) > 1e-3  # ~0.3 deg drift by 2026

    # and it must match a direct skyfield of-date computation for the same Star
    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    star = Star(ra_hours=83.82 / 15.0, dec_degrees=-5.39)
    t = ts.from_datetime(when)
    ra, dec, _ = eph["earth"].at(t).observe(star).apparent().radec(epoch="date")
    assert math.isclose(ra_ofdate, ra.degrees % 360.0, abs_tol=1e-6)
```

- [ ] **Step 2: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_fixed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.compute.fixed'`.

- [ ] **Step 3: Implémenter `fixed.py`**

Create `oracle/oracle/compute/fixed.py`:

```python
"""Project fixed-object positions from J2000 to apparent of-date (JNow)."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from skyfield.api import Loader, Star


def project_to_of_date(
    points: list[tuple[str, float, float]],
    kernel_path: Path,
    when_utc: datetime,
) -> dict[str, tuple[float, float]]:
    """Map each ``(id, ra_deg_j2000, dec_deg_j2000)`` to ``(ra_deg, dec_deg)`` of-date.

    Vectorised: one instant, N objects. Consumers never do precession/nutation,
    so the artifact stores JNow positions computed here at generation time.
    """
    if not points:
        return {}
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    else:
        when_utc = when_utc.astimezone(timezone.utc)

    ids = [p[0] for p in points]
    ra_hours = np.array([p[1] / 15.0 for p in points])
    dec_degrees = np.array([p[2] for p in points])

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    earth = eph["earth"]
    t = ts.from_datetime(when_utc)

    star = Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
    ra, dec, _ = earth.at(t).observe(star).apparent().radec(epoch="date")
    return {
        i: (float(r) % 360.0, float(d))
        for i, r, d in zip(ids, ra.degrees, dec.degrees)
    }
```

- [ ] **Step 4: Lancer le test — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_fixed.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/compute/fixed.py oracle/tests/test_fixed.py
git commit -m "feat(oracle): J2000 to of-date projection for fixed objects

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Éphéméride planètes + Lune + Soleil

Calcule l'éphéméride pré-calculée (samples journaliers) des 9 corps du kernel `de421.bsp` : Mercure, Vénus, Mars, Jupiter, Saturne, Uranus, Neptune, Lune, Soleil. Magnitude via `planetary_magnitude` (7 planètes), phase via `fraction_illuminated` (Lune/Vénus/Mercure). No-fetch, 100 % déterministe.

**Files:**
- Create: `oracle/oracle/compute/planets.py`
- Test: `oracle/tests/test_planets.py`

**Interfaces:**
- Produces:
  - `compute.planets.compute_planet_ephemeris(kernel_path: Path, start_utc: datetime, days: int = 60) -> tuple[list[ObjectRow], list[EphemRow]]`
  - `compute.planets.BODIES: list[Body]` (internal config; `Body(id, kind, name, target, mag, illum)`)
- Consumes: `records.ObjectRow`, `records.EphemRow`, kernel `de421.bsp`, `skyfield.magnitudelib.planetary_magnitude`.

- [ ] **Step 1: Écrire le test (échoue)**

Create `oracle/tests/test_planets.py`:

```python
from datetime import datetime, timezone

from oracle.compute.planets import compute_planet_ephemeris


def test_nine_bodies_over_window(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    objects, rows = compute_planet_ephemeris(kernel_path, start, days=3)
    ids = {o.id for o in objects}
    assert ids == {
        "planet:mercury", "planet:venus", "planet:mars", "planet:jupiter",
        "planet:saturn", "planet:uranus", "planet:neptune", "moon", "sun",
    }
    assert len({o.kind for o in objects}) == 3  # planet / moon / sun
    assert len(rows) == 9 * 3  # 9 bodies x 3 daily samples


def test_planet_ranges_and_magnitude(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    _, rows = compute_planet_ephemeris(kernel_path, start, days=2)
    for r in rows:
        assert 0.0 <= r.ra_deg < 360.0
        assert -90.0 <= r.dec_deg <= 90.0
        assert r.sample_utc.endswith("Z")
    # Mars carries a real apparent magnitude (planetary_magnitude)
    mars = [r for r in rows if r.object_id == "planet:mars"]
    assert all(r.apparent_mag is not None for r in mars)


def test_moon_has_illumination_planets_may_not(kernel_path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    _, rows = compute_planet_ephemeris(kernel_path, start, days=1)
    moon = next(r for r in rows if r.object_id == "moon")
    assert moon.illumination is not None and 0.0 <= moon.illumination <= 1.0
    jupiter = next(r for r in rows if r.object_id == "planet:jupiter")
    assert jupiter.illumination is None
    # the Sun has no "distance to Sun"
    sun = next(r for r in rows if r.object_id == "sun")
    assert sun.sun_dist_au is None
```

- [ ] **Step 2: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_planets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.compute.planets'`.

- [ ] **Step 3: Implémenter `planets.py`**

`planetary_magnitude` supports the 8 planets (not Moon/Sun) and takes an astrometric position (`.observe()` without `.apparent()`). `fraction_illuminated(sun)` is a position method. The Sun's `sun_dist_au` is left `None` (a body has no distance to itself).

Create `oracle/oracle/compute/planets.py`:

```python
"""Compute daily apparent (of-date) ephemeris for planets, Moon and Sun."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from skyfield.api import Loader, load_constellation_map, position_of_radec
from skyfield.magnitudelib import planetary_magnitude

from oracle.records import EphemRow, ObjectRow


@dataclass(frozen=True)
class Body:
    """One de421 target and how to describe it in the catalogue."""

    id: str
    kind: str  # planet | moon | sun
    name: str
    target: str  # de421 body key
    mag: bool  # compute apparent magnitude via planetary_magnitude
    illum: bool  # compute illuminated fraction via fraction_illuminated


# Pluto is excluded on purpose (mag ~14, out of reach of a 127 mm; de421 has
# only its barycentre).
BODIES: list[Body] = [
    Body("planet:mercury", "planet", "Mercury", "mercury", True, True),
    Body("planet:venus", "planet", "Venus", "venus", True, True),
    Body("planet:mars", "planet", "Mars", "mars", True, False),
    Body("planet:jupiter", "planet", "Jupiter", "jupiter barycenter", True, False),
    Body("planet:saturn", "planet", "Saturn", "saturn barycenter", True, False),
    Body("planet:uranus", "planet", "Uranus", "uranus barycenter", True, False),
    Body("planet:neptune", "planet", "Neptune", "neptune barycenter", True, False),
    Body("moon", "moon", "Moon", "moon", False, True),
    Body("sun", "sun", "Sun", "sun", False, False),
]


def compute_planet_ephemeris(
    kernel_path: Path,
    start_utc: datetime,
    days: int = 60,
) -> tuple[list[ObjectRow], list[EphemRow]]:
    """Daily apparent RA/Dec (of-date) for every body in ``BODIES`` over ``days`` days."""
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    else:
        start_utc = start_utc.astimezone(timezone.utc)

    loader = Loader(str(kernel_path.parent))
    eph = loader(kernel_path.name)
    ts = loader.timescale()
    sun, earth = eph["sun"], eph["earth"]
    constellation_at = load_constellation_map()

    objects = [ObjectRow(id=b.id, kind=b.kind, name=b.name, designation=None) for b in BODIES]

    rows: list[EphemRow] = []
    for b in BODIES:
        target = eph[b.target]
        for day in range(days):
            when = start_utc + timedelta(days=day)
            t = ts.from_datetime(when)
            astrometric = earth.at(t).observe(target)
            apparent = astrometric.apparent()
            ra, dec, delta = apparent.radec(epoch="date")
            mag = float(planetary_magnitude(astrometric)) if b.mag else None
            illum = float(apparent.fraction_illuminated(sun)) if b.illum else None
            sun_dist = (
                None if b.kind == "sun"
                else float(sun.at(t).observe(target).distance().au)
            )
            try:
                const = constellation_at(position_of_radec(ra.hours, dec.degrees))
            except Exception:
                const = None
            rows.append(
                EphemRow(
                    object_id=b.id,
                    sample_utc=when.isoformat().replace("+00:00", "Z"),
                    ra_deg=ra.degrees % 360.0,
                    dec_deg=dec.degrees,
                    earth_dist_au=float(delta.au),
                    sun_dist_au=sun_dist,
                    apparent_mag=mag,
                    illumination=illum,
                    constellation=const,
                )
            )
    return objects, rows
```

- [ ] **Step 4: Lancer le test — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_planets.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/compute/planets.py oracle/tests/test_planets.py
git commit -m "feat(oracle): planet/Moon/Sun ephemeris from de421

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Orchestration `build.py` — pipeline unifié

Réécrit `build.py` pour assembler toutes les familles en un seul artefact v2 : fetch (3 sources + fallback), compute (comètes + planètes + projection fixes), writer unifié, manifest.

**Files:**
- Modify: `oracle/oracle/build.py` (réécriture de la fonction `build`)
- Test: `oracle/tests/test_build_pipeline.py` (réécriture)

**Interfaces:**
- Produces: `build.build(out_dir, start_utc, *, days=60, sqlite_url, fetch=True) -> tuple[Path, Path]` (signature inchangée ; contenu unifié).
- Consumes: tout ce qui précède — `fetch_comet_els`/`load_comets`/`comet_objects`, `fetch_open_ngc`/`load_deep_sky`, `fetch_iau_csn`/`load_stars`, `compute_ephemeris`, `compute_planet_ephemeris`, `project_to_of_date`, `build_reference_db`, `write_manifest`.

- [ ] **Step 1: Réécrire le test pipeline (échoue)**

Replace the entire contents of `oracle/tests/test_build_pipeline.py`:

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build


def test_full_pipeline_offline_all_families(tmp_path: Path) -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    sqlite_path, manifest_path = build(
        tmp_path,
        start,
        days=3,
        sqlite_url="https://example/reference.sqlite",
        fetch=False,  # use bundled fallbacks: fully offline, deterministic
    )
    assert sqlite_path.exists() and manifest_path.exists()

    con = sqlite3.connect(sqlite_path)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == 2
        kinds = {k for (k,) in con.execute("SELECT DISTINCT kind FROM objects")}
        assert kinds == {"comet", "planet", "moon", "sun", "dso", "star"}
        # every family produced rows in its target table
        assert con.execute("SELECT COUNT(*) FROM fixed_object").fetchone()[0] > 10000
        assert con.execute("SELECT COUNT(*) FROM ephemeris").fetchone()[0] > 0
        assert con.execute("SELECT COUNT(*) FROM comet_elements").fetchone()[0] > 0
        # 9 ephemeral bodies from de421 present
        (n_bodies,) = con.execute(
            "SELECT COUNT(*) FROM objects WHERE kind IN ('planet','moon','sun')"
        ).fetchone()
        assert n_bodies == 9
        # Messier fully covered
        (n_messier,) = con.execute(
            "SELECT COUNT(DISTINCT messier) FROM fixed_object WHERE messier IS NOT NULL"
        ).fetchone()
        assert n_messier == 110
        # global FK integrity across all child tables
        for child in ("fixed_object", "ephemeris", "comet_elements"):
            (orphans,) = con.execute(
                f"SELECT COUNT(*) FROM {child} c "
                f"LEFT JOIN objects o ON c.object_id = o.id WHERE o.id IS NULL"
            ).fetchone()
            assert orphans == 0, child
    finally:
        con.close()
```

- [ ] **Step 2: Lancer le test — vérifier l'échec**

Run: `cd oracle && uv run pytest tests/test_build_pipeline.py -v`
Expected: FAIL — le `build` actuel ne peuple ni `fixed_object`, ni les planètes, ni le schéma v2 (l'appel à `build_reference_db` a l'ancienne signature).

- [ ] **Step 3: Réécrire `build.py`**

Replace the entire contents of `oracle/oracle/build.py`:

```python
"""End-to-end unified reference build pipeline (all object families)."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import oracle
from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.compute.fixed import project_to_of_date
from oracle.compute.planets import compute_planet_ephemeris
from oracle.manifest import write_manifest
from oracle.records import FixedRow, ObjectRow
from oracle.sources.comets import comet_objects, fetch_comet_els, load_comets
from oracle.sources.deep_sky import fetch_open_ngc, load_deep_sky
from oracle.sources.stars import fetch_iau_csn, load_stars


def _fetch_or_copy(fetch: bool, fetcher, dest: Path, fallback_name: str) -> Path:
    """Fetch to ``dest`` when online, else copy the bundled fallback."""
    if fetch:
        return fetcher(dest)
    shutil.copyfile(oracle.data_dir() / fallback_name, dest)
    return dest


def build(
    out_dir: Path,
    start_utc: datetime,
    *,
    days: int = 60,
    sqlite_url: str,
    fetch: bool = True,
) -> tuple[Path, Path]:
    """Run fetch→load→compute→build_db→manifest for every family; return (sqlite, manifest)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    kernel_path = oracle.data_dir() / "de421.bsp"

    # --- fetch (3 sources; each falls back to a bundled snapshot) ---
    els_path = _fetch_or_copy(fetch, fetch_comet_els, out_dir / "CometEls.txt", "CometEls.fallback.txt")
    ngc_path = _fetch_or_copy(fetch, fetch_open_ngc, out_dir / "OpenNGC.csv", "OpenNGC.fallback.csv")
    csn_path = _fetch_or_copy(fetch, fetch_iau_csn, out_dir / "IAU-CSN.txt", "IAU-CSN.fallback.txt")

    # --- load ---
    comets = load_comets(els_path)
    deep_sky = load_deep_sky(ngc_path)
    stars = load_stars(csn_path)

    # --- compute ephemeral families ---
    comet_ephem = compute_ephemeris(comets, kernel_path, start_utc, days=days)
    comet_objs, comet_elems = comet_objects(comets)
    planet_objs, planet_ephem = compute_planet_ephemeris(kernel_path, start_utc, days=days)

    # --- project fixed families to of-date at generation time ---
    fixed_points = (
        [(r.id, r.ra_deg_j2000, r.dec_deg_j2000) for r in deep_sky]
        + [(s.id, s.ra_deg_j2000, s.dec_deg_j2000) for s in stars]
    )
    projected = project_to_of_date(fixed_points, kernel_path, start_utc)

    objects: list[ObjectRow] = list(comet_objs) + list(planet_objs)
    fixed: list[FixedRow] = []
    for r in deep_sky:
        ra, dec = projected[r.id]
        objects.append(ObjectRow(id=r.id, kind="dso", name=r.name, designation=r.designation))
        fixed.append(
            FixedRow(
                object_id=r.id, ra_deg=ra, dec_deg=dec, apparent_mag=r.apparent_mag,
                object_type=r.object_type, size_arcmin=r.size_arcmin,
                constellation=r.constellation, messier=r.messier, ngc_ic=r.ngc_ic,
            )
        )
    for s in stars:
        ra, dec = projected[s.id]
        objects.append(ObjectRow(id=s.id, kind="star", name=s.name, designation=s.designation))
        fixed.append(
            FixedRow(
                object_id=s.id, ra_deg=ra, dec_deg=dec, apparent_mag=s.apparent_mag,
                object_type="star", size_arcmin=None,
                constellation=s.constellation, messier=None, ngc_ic=None,
            )
        )

    ephem = list(comet_ephem) + list(planet_ephem)

    # --- meta / write / manifest ---
    now_iso = start_utc.isoformat().replace("+00:00", "Z")
    end_iso = (start_utc + timedelta(days=days - 1)).isoformat().replace("+00:00", "Z")
    meta = BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now_iso,
        mpc_epoch=None,
        window_start=now_iso,
        window_end=end_iso,
        skyfield_kernel="de421.bsp",
    )
    sqlite_path = build_reference_db(
        out_dir / "reference.sqlite", objects, fixed, ephem, comet_elems, meta
    )
    manifest_path = out_dir / "manifest.json"
    write_manifest(sqlite_path, manifest_path, meta, sqlite_url)
    return sqlite_path, manifest_path
```

- [ ] **Step 4: Lancer le test — vérifier le succès**

Run: `cd oracle && uv run pytest tests/test_build_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Lancer toute la suite**

Run: `cd oracle && uv run pytest tests/ -v`
Expected: PASS (tous les fichiers de test). Corriger tout résidu de champ renommé avant de continuer.

- [ ] **Step 6: Commit**

```bash
git add oracle/oracle/build.py oracle/tests/test_build_pipeline.py
git commit -m "feat(oracle): unified build pipeline (all object families)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Mise à jour du contrat `README.md` (schéma v2)

Met à jour le contrat consommateur pour refléter le schéma v2 (les consommateurs ne lisent que `README.md` + `schema.sql`).

**Files:**
- Modify: `oracle/README.md`

**Interfaces:** aucune (documentation).

- [ ] **Step 1: Réécrire les sections concernées de `README.md`**

Replace the "## What it does" and "## The contract" sections of `oracle/README.md` with:

```markdown
## What it does
Fetch reference data (MPC comets, OpenNGC deep-sky, IAU-CSN named stars) +
de421 kernel (planets/Moon/Sun) → skyfield → SQLite v2 → manifest.
- **Fixed objects** (deep-sky, stars): one RA/Dec, apparent of-date (JNow).
- **Ephemeral objects** (comets, planets, Moon, Sun): daily apparent RA/Dec,
  of-date, 60-day rolling window. Interpolate linearly between samples.

## The contract (consumers read only this)
- `manifest.json`: `{ schema_version, generated_at, sqlite_url, sqlite_sha256,
  window_start, window_end }`. Poll it; download the SQLite only when
  `sqlite_sha256` changes. Refuse a `schema_version` newer than you support.
- `reference.sqlite` (`schema_version = 2`): tables `meta`, `objects`,
  `fixed_object`, `ephemeris`, `comet_elements` (see `schema.sql`). Every
  `fixed_object` / `ephemeris` / `comet_elements` row references `objects(id)`;
  `objects.kind` is one of `comet | planet | moon | sun | dso | star`.
  **All RA/Dec are apparent, of-date (JNow)** — consumers do only LST→alt/az.
- `apparent_mag` is **reliable for planets/luminaries** but an **estimate for
  comets** (outbursts). By convention, treat `kind = comet` magnitudes as an
  estimate; never a hard filter. `illumination` is set for the Moon/Venus/Mercury.
- The **base is complete and tube-agnostic**: no magnitude/size/type pre-filter
  is applied by the producer. Filtering "what my tube shows" is a consumer
  decision.
```

- [ ] **Step 2: Commit**

```bash
git add oracle/README.md
git commit -m "docs(oracle): README contract for schema v2 common base

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notes d'exécution transverses

- **Docs projet** (à faire dans la session qui exécute, cf. conventions) : ajouter une entrée journal (`docs/project/journal.md`) résumant SP1 et son livrable, et vérifier que `docs/project/roadmap.md` reflète l'extension Oracle (base commune). Non inclus comme tâche TDD car documentaire ; à committer séparément.
- **CI inchangée** : `.github/workflows/oracle.yml` republie l'artefact v2 sous `almanac-latest` sans modification de mécanique. Après merge, un run manuel (workflow_dispatch) valide le build v2 réel (fetch en ligne des 3 sources).
- **SP2/SP3 hors périmètre** : la suppression de `backend/.../seed_stars.sql` et la bascule du backend sur la lecture de `reference.sqlite` sont SP2, pas ici.

## Self-Review (effectuée)

- **Couverture spec** : schéma v2 (T1) ✓ ; comètes restructurées objects+comet_elements+ephemeris (T1) ✓ ; helper fetch+fallback unique + refactor comets (T2) ✓ ; deep-sky OpenNGC + Messier cross-ref (T3) ✓ ; étoiles IAU-CSN fetch (T4) ✓ ; projection fixes of-date (T5) ✓ ; planètes/Lune/Soleil, planetary_magnitude, fraction_illuminated, Pluton exclu (T6) ✓ ; orchestration + fallbacks (T7) ✓ ; README v2 (T8) ✓ ; tests par famille + FK + Messier=110 + 9 corps + of-date guards ✓.
- **Placeholders** : aucun — chaque étape porte le code réel et les commandes exactes.
- **Cohérence des types** : `EphemRow`/`ObjectRow`/`FixedRow`/`CometElements` définis en T1 et consommés à l'identique en T6/T7 ; `object_id` uniforme ; `build_reference_db` même signature partout ; `project_to_of_date` renvoie `dict[id → (ra, dec)]` consommé tel quel en T7 ; `fetch_with_fallback` (T2) réutilisé par les 3 sources fetchables (T2 comets, T3 deep-sky, T4 stars).
