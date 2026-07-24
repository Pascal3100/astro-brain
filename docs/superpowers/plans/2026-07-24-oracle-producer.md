# Oracle Producer (`oracle/`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `oracle/` module that fetches fresh comet orbital elements from the MPC, computes their ephemeris with skyfield, and publishes a versioned `reference.sqlite` + `manifest.json` from a GitHub Actions cron job.

**Architecture:** A standalone Python package under `oracle/` (pair of `backend/` and `app/`, zero dependency on either). A batch pipeline: `fetch MPC CometEls → skyfield ephemeris over a rolling window → build SQLite → write manifest`. Runs only in CI, never on the Pi. The SQLite schema is the sole interface with consumers.

**Tech Stack:** Python 3.13, `uv`, `skyfield` (+ `pandas`, pulled by `load_comets_dataframe`), `sqlite3` (stdlib), GitHub Actions.

## Global Constraints

- **Python 3.13**, tooling via `uv` (venv + lockfile), mirroring `backend/`. All commands run from `oracle/`.
- **PEP compliance** (PEP 8, 257, 484/604 type hints) — house rule for all Python.
- **Zero dependency on `backend/` or `app/`** — `oracle/` imports nothing from them.
- **The SQLite schema is the contract.** `schema.sql` is its source of truth; `meta.schema_version` starts at **1** and increments only on schema change.
- **RA/Dec stored = apparent, of-date (JNow) at each sample instant** (decision for spec Q1): consumers do only LST→alt/az trig, and the values align with the GoTo `EQUATORIAL_EOD_COORD` (JNow). Astrometric is not stored.
- **Sampling = daily, linear interpolation downstream** (decision for spec Q2). Adaptive sampling is out of scope.
- **Ephemeris window = 60 days** starting at the generation date (rolling).
- **Ephemeris kernel = `de421.bsp`**, committed at `oracle/data/de421.bsp` (~16 MB, never changes) so tests and CI are fully offline and deterministic.
- **Predicted magnitude is an estimate** (comet outbursts) — computed and stored, never used as a hard filter.
- **MPC fetch must never fail the build**: on any fetch error, fall back to a bundled `oracle/data/CometEls.fallback.txt`.
- Spec Q3 (notif site) and Q4 (Flutter folder) belong to the **consumer** plans, not this one.

---

### Task 1: Scaffold the `oracle/` package

**Files:**
- Create: `oracle/pyproject.toml`
- Create: `oracle/oracle/__init__.py`
- Create: `oracle/tests/test_smoke.py`
- Create: `oracle/.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable package `oracle` and a green `uv run pytest`.

- [ ] **Step 1: Write the failing test**

```python
# oracle/tests/test_smoke.py
import oracle


def test_package_exposes_version() -> None:
    assert isinstance(oracle.__version__, str)
    assert oracle.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd oracle && uv run pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle'` (package not yet installed).

- [ ] **Step 3: Write the minimal package + config**

```toml
# oracle/pyproject.toml
[project]
name = "oracle"
version = "0.1.0"
description = "Astro-Brain reference data generator (comets, events) -> reference.sqlite"
requires-python = ">=3.13"
dependencies = [
    "skyfield>=1.49",
    "pandas>=2.2",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["oracle"]
```

```python
# oracle/oracle/__init__.py
"""Astro-Brain reference data generator."""

__version__ = "0.1.0"
```

```gitignore
# oracle/.gitignore
.venv/
__pycache__/
*.pyc
dist/
/build_output/
```

- [ ] **Step 4: Sync and run the test to verify it passes**

Run: `cd oracle && uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/pyproject.toml oracle/oracle/__init__.py oracle/tests/test_smoke.py oracle/.gitignore oracle/uv.lock
git commit -m "feat(oracle): scaffold reference-data generator package"
```

---

### Task 2: Commit the ephemeris kernel + a comet fixture

**Files:**
- Create: `oracle/data/de421.bsp` (binary, downloaded once)
- Create: `oracle/data/CometEls.fallback.txt` (a real MPC snapshot, doubles as test fixture)
- Create: `oracle/tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `KERNEL_PATH` and `FALLBACK_COMETS_PATH` pytest fixtures returning `pathlib.Path`, and a `data_dir()` helper on the package.

- [ ] **Step 1: Download the kernel and a comet snapshot into `oracle/data/`**

Run (one-time, network needed):
```bash
cd oracle && mkdir -p data
python -c "from skyfield.api import Loader; Loader('data').download('de421.bsp')"
curl -sSL "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt" -o data/CometEls.fallback.txt
```
Expected: `oracle/data/de421.bsp` (~16 MB) and a non-empty `CometEls.fallback.txt` (fixed-width MPC records).

- [ ] **Step 2: Write the failing test for the data-dir helper + fixtures**

```python
# oracle/tests/conftest.py
from pathlib import Path

import pytest

import oracle


@pytest.fixture
def kernel_path() -> Path:
    return oracle.data_dir() / "de421.bsp"


@pytest.fixture
def fallback_comets_path() -> Path:
    return oracle.data_dir() / "CometEls.fallback.txt"
```

```python
# oracle/tests/test_data.py
def test_kernel_and_fallback_present(kernel_path, fallback_comets_path) -> None:
    assert kernel_path.exists() and kernel_path.stat().st_size > 1_000_000
    assert fallback_comets_path.exists()
    assert fallback_comets_path.read_text().strip()
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_data.py -v`
Expected: FAIL — `AttributeError: module 'oracle' has no attribute 'data_dir'`.

- [ ] **Step 4: Implement `data_dir()`**

```python
# oracle/oracle/__init__.py
"""Astro-Brain reference data generator."""

from pathlib import Path

__version__ = "0.1.0"


def data_dir() -> Path:
    """Return the bundled data directory (kernel + fallback comet elements)."""
    return Path(__file__).resolve().parent.parent / "data"
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_data.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add oracle/data/de421.bsp oracle/data/CometEls.fallback.txt oracle/tests/conftest.py oracle/tests/test_data.py oracle/oracle/__init__.py
git commit -m "feat(oracle): bundle de421 kernel + MPC comet fallback snapshot"
```

---

### Task 3: Load and deduplicate comet elements

**Files:**
- Create: `oracle/oracle/sources/__init__.py`
- Create: `oracle/oracle/sources/comets.py`
- Create: `oracle/tests/test_comets_load.py`

**Interfaces:**
- Consumes: `fallback_comets_path` fixture (Task 2).
- Produces: `load_comets(path: Path) -> pandas.DataFrame` — one row per comet, indexed by `designation`, with the columns skyfield's `mpc.load_comets_dataframe` yields (`designation`, `perihelion_distance_au`, `eccentricity`, `inclination_degrees`, `argument_of_perihelion_degrees`, `longitude_of_ascending_node_degrees`, `perihelion_year/month/day`, `magnitude_g`, `magnitude_k`, `reference`, …).

- [ ] **Step 1: Write the failing test**

```python
# oracle/tests/test_comets_load.py
from oracle.sources.comets import load_comets


def test_load_comets_returns_unique_designations(fallback_comets_path) -> None:
    df = load_comets(fallback_comets_path)
    assert len(df) > 0
    # dedup: one orbit per comet
    assert df.index.is_unique
    assert df.index.name == "designation"
    # sanity on required orbital columns
    for col in ("perihelion_distance_au", "eccentricity", "inclination_degrees"):
        assert col in df.columns
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_comets_load.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.sources'`.

- [ ] **Step 3: Implement the loader**

```python
# oracle/oracle/sources/__init__.py
```

```python
# oracle/oracle/sources/comets.py
"""Load comet orbital elements from an MPC CometEls.txt file."""

from pathlib import Path

import pandas as pd
from skyfield.api import load
from skyfield.data import mpc


def load_comets(path: Path) -> pd.DataFrame:
    """Parse an MPC CometEls.txt file into a de-duplicated DataFrame.

    Keeps only the most recent orbit per comet (MPC ships multiple epochs),
    indexed by ``designation``.
    """
    with load.open(str(path)) as f:
        comets = mpc.load_comets_dataframe(f)
    comets = (
        comets.sort_values("reference")
        .groupby("designation", as_index=False)
        .last()
        .set_index("designation", drop=False)
    )
    comets.index.name = "designation"
    return comets
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_comets_load.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/sources/ oracle/tests/test_comets_load.py
git commit -m "feat(oracle): load + dedupe MPC comet elements via skyfield"
```

---

### Task 4: Fetch with bundled fallback

**Files:**
- Modify: `oracle/oracle/sources/comets.py`
- Create: `oracle/tests/test_comets_fetch.py`

**Interfaces:**
- Consumes: `load_comets` (Task 3), `oracle.data_dir()` (Task 2).
- Produces: `fetch_comet_els(dest: Path, url: str = COMET_ELS_URL, *, opener=urllib.request.urlopen) -> Path` — writes fresh elements to `dest` on success, copies the bundled fallback to `dest` on any error; always returns `dest`. Module constant `COMET_ELS_URL: str`.

- [ ] **Step 1: Write the failing tests (success + fallback)**

```python
# oracle/tests/test_comets_fetch.py
from pathlib import Path

from oracle.sources.comets import fetch_comet_els


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def test_fetch_writes_remote_body(tmp_path: Path) -> None:
    dest = tmp_path / "CometEls.txt"

    def opener(url):  # noqa: ANN001
        return _FakeResponse(b"FRESH-CONTENT")

    result = fetch_comet_els(dest, opener=opener)
    assert result == dest
    assert dest.read_bytes() == b"FRESH-CONTENT"


def test_fetch_falls_back_on_error(tmp_path: Path) -> None:
    dest = tmp_path / "CometEls.txt"

    def opener(url):  # noqa: ANN001
        raise OSError("network down")

    result = fetch_comet_els(dest, opener=opener)
    assert result == dest
    # fell back to the bundled snapshot -> non-empty file
    assert dest.stat().st_size > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_comets_fetch.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_comet_els'`.

- [ ] **Step 3: Implement the fetcher**

```python
# add to oracle/oracle/sources/comets.py
import shutil
import urllib.request
from collections.abc import Callable

import oracle

COMET_ELS_URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"


def fetch_comet_els(
    dest: Path,
    url: str = COMET_ELS_URL,
    *,
    opener: Callable[[str], object] = urllib.request.urlopen,
) -> Path:
    """Fetch fresh comet elements to ``dest``; fall back to the bundled snapshot.

    A build must never fail because the MPC is unreachable.
    """
    try:
        with opener(url) as response:  # type: ignore[attr-defined]
            body = response.read()
        if not body:
            raise OSError("empty response body")
        dest.write_bytes(body)
    except Exception:
        fallback = oracle.data_dir() / "CometEls.fallback.txt"
        shutil.copyfile(fallback, dest)
    return dest
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_comets_fetch.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/sources/comets.py oracle/tests/test_comets_fetch.py
git commit -m "feat(oracle): fetch comet elements with bundled fallback"
```

---

### Task 5: Compute the ephemeris (skyfield)

**Files:**
- Create: `oracle/oracle/compute/__init__.py`
- Create: `oracle/oracle/compute/ephemeris.py`
- Create: `oracle/tests/test_ephemeris.py`

**Interfaces:**
- Consumes: `load_comets` (Task 3), `kernel_path`/`fallback_comets_path` fixtures (Task 2).
- Produces:
  - dataclass `EphemRow(comet_id: str, sample_utc: str, ra_deg: float, dec_deg: float, earth_dist_au: float, sun_dist_au: float, predicted_mag: float | None, constellation: str | None)`
  - `predicted_magnitude(g: float, k: float, earth_dist_au: float, sun_dist_au: float) -> float`
  - `compute_ephemeris(comets, kernel_path, start_utc: datetime, days: int = 60) -> list[EphemRow]` — daily apparent (of-date) RA/Dec per comet.

- [ ] **Step 1: Write the failing tests**

```python
# oracle/tests/test_ephemeris.py
import math
from datetime import datetime, timezone

from oracle.compute.ephemeris import (
    compute_ephemeris,
    predicted_magnitude,
)
from oracle.sources.comets import load_comets


def test_predicted_magnitude_formula() -> None:
    # m = g + 5*log10(delta) + 2.5*k*log10(r)
    m = predicted_magnitude(g=5.0, k=4.0, earth_dist_au=1.0, sun_dist_au=1.0)
    assert m == 5.0  # log10(1) == 0
    m2 = predicted_magnitude(g=5.0, k=4.0, earth_dist_au=10.0, sun_dist_au=1.0)
    assert math.isclose(m2, 5.0 + 5.0, rel_tol=1e-9)


def test_compute_ephemeris_shape_and_ranges(kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=5)
    # 3 comets x 5 daily samples
    assert len(rows) == 15
    for r in rows:
        assert 0.0 <= r.ra_deg < 360.0
        assert -90.0 <= r.dec_deg <= 90.0
        assert r.earth_dist_au > 0.0
        assert r.sun_dist_au > 0.0
        assert r.comet_id in set(comets.index)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_ephemeris.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.compute'`.

- [ ] **Step 3: Implement the computation**

```python
# oracle/oracle/compute/__init__.py
```

```python
# oracle/oracle/compute/ephemeris.py
"""Compute daily apparent (of-date) comet ephemeris with skyfield."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from skyfield.api import Loader, load_constellation_map, position_of_radec
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN
from skyfield.data import mpc


@dataclass(frozen=True)
class EphemRow:
    comet_id: str
    sample_utc: str  # ISO-8601 UTC
    ra_deg: float
    dec_deg: float
    earth_dist_au: float
    sun_dist_au: float
    predicted_mag: float | None
    constellation: str | None


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
                    comet_id=str(designation),
                    sample_utc=when.isoformat().replace("+00:00", "Z"),
                    ra_deg=ra._degrees % 360.0,
                    dec_deg=dec.degrees,
                    earth_dist_au=delta.au,
                    sun_dist_au=r.au,
                    predicted_mag=mag,
                    constellation=const,
                )
            )
    return rows
```

> Note for the implementer: skyfield's `radec()` returns `Angle` objects — `ra._degrees` and `dec.degrees` are the degree accessors, `ra.hours` the hour accessor. If a skyfield version differs, adjust the accessor but keep the test's range assertions as the contract.

- [ ] **Step 4: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_ephemeris.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/compute/ oracle/tests/test_ephemeris.py
git commit -m "feat(oracle): compute daily apparent comet ephemeris via skyfield"
```

---

### Task 6: Define the schema + build `reference.sqlite`

**Files:**
- Create: `oracle/schema.sql`
- Create: `oracle/oracle/build_db.py`
- Create: `oracle/tests/test_build_db.py`

**Interfaces:**
- Consumes: `EphemRow` (Task 5), a `comets` DataFrame (Task 3).
- Produces:
  - dataclass `BuildMeta(schema_version: int, generated_at: str, mpc_epoch: str | None, window_start: str, window_end: str, skyfield_kernel: str)`
  - `SCHEMA_VERSION: int = 1`
  - `build_reference_db(out_path: Path, comets, ephem_rows: list[EphemRow], meta: BuildMeta) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# oracle/tests/test_build_db.py
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.sources.comets import load_comets


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


def test_build_db_is_queryable(tmp_path: Path, kernel_path, fallback_comets_path) -> None:
    comets = load_comets(fallback_comets_path).head(3)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = compute_ephemeris(comets, kernel_path, start, days=4)

    out = build_reference_db(tmp_path / "reference.sqlite", comets, rows, _meta())
    assert out.exists()

    con = sqlite3.connect(out)
    try:
        (version,) = con.execute("SELECT schema_version FROM meta").fetchone()
        assert version == SCHEMA_VERSION
        (n_comets,) = con.execute("SELECT COUNT(*) FROM comets").fetchone()
        assert n_comets == 3
        (n_ephem,) = con.execute("SELECT COUNT(*) FROM comet_ephemeris").fetchone()
        assert n_ephem == 12  # 3 comets x 4 samples
        # every ephemeris row references an existing comet (FK integrity)
        (orphans,) = con.execute(
            "SELECT COUNT(*) FROM comet_ephemeris e "
            "LEFT JOIN comets c ON e.comet_id = c.id WHERE c.id IS NULL"
        ).fetchone()
        assert orphans == 0
    finally:
        con.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_build_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.build_db'`.

- [ ] **Step 3: Write the schema**

```sql
-- oracle/schema.sql  (the contract; meta.schema_version gates compatibility)
CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,
  generated_at     TEXT    NOT NULL,
  mpc_epoch        TEXT,
  window_start     TEXT    NOT NULL,
  window_end       TEXT    NOT NULL,
  skyfield_kernel  TEXT
);

CREATE TABLE comets (
  id                  TEXT PRIMARY KEY,
  designation         TEXT NOT NULL,
  name                TEXT,
  epoch_jd            REAL,
  perihelion_q_au     REAL NOT NULL,
  eccentricity        REAL NOT NULL,
  inclination_deg     REAL NOT NULL,
  arg_perihelion_deg  REAL NOT NULL,
  node_deg            REAL NOT NULL,
  mag_h               REAL,
  mag_k               REAL
);

CREATE TABLE comet_ephemeris (
  comet_id       TEXT NOT NULL REFERENCES comets(id),
  sample_utc     TEXT NOT NULL,
  ra_deg         REAL NOT NULL,
  dec_deg        REAL NOT NULL,
  earth_dist_au  REAL NOT NULL,
  sun_dist_au    REAL NOT NULL,
  predicted_mag  REAL,
  constellation  TEXT,
  PRIMARY KEY (comet_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON comet_ephemeris(sample_utc);
```

- [ ] **Step 4: Implement the builder**

```python
# oracle/oracle/build_db.py
"""Build the reference.sqlite artifact from comets + ephemeris rows."""

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

import oracle
from oracle.compute.ephemeris import EphemRow

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BuildMeta:
    schema_version: int
    generated_at: str
    mpc_epoch: str | None
    window_start: str
    window_end: str
    skyfield_kernel: str


def _schema_sql() -> str:
    return (Path(oracle.__file__).resolve().parent.parent / "schema.sql").read_text()


def _opt(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    return float(value) if pd.notna(value) else None


def build_reference_db(
    out_path: Path,
    comets: pd.DataFrame,
    ephem_rows: list[EphemRow],
    meta: BuildMeta,
) -> Path:
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
            "INSERT INTO comets (id, designation, name, epoch_jd, perihelion_q_au, "
            "eccentricity, inclination_deg, arg_perihelion_deg, node_deg, mag_h, "
            "mag_k) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    str(designation),
                    str(row.get("designation", designation)),
                    (str(row["name"]) if pd.notna(row.get("name")) else None),
                    _opt(row, "epoch_jd"),
                    _opt(row, "perihelion_distance_au"),
                    _opt(row, "eccentricity"),
                    _opt(row, "inclination_degrees"),
                    _opt(row, "argument_of_perihelion_degrees"),
                    _opt(row, "longitude_of_ascending_node_degrees"),
                    _opt(row, "magnitude_g"),
                    _opt(row, "magnitude_k"),
                )
                for designation, row in comets.iterrows()
            ],
        )
        con.executemany(
            "INSERT INTO comet_ephemeris (comet_id, sample_utc, ra_deg, dec_deg, "
            "earth_dist_au, sun_dist_au, predicted_mag, constellation) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    r.comet_id,
                    r.sample_utc,
                    r.ra_deg,
                    r.dec_deg,
                    r.earth_dist_au,
                    r.sun_dist_au,
                    r.predicted_mag,
                    r.constellation,
                )
                for r in ephem_rows
            ],
        )
        con.commit()
    finally:
        con.close()
    return out_path
```

> Note: `comets` may not carry a `name` or `epoch_jd` column depending on the MPC file; `_opt`/`row.get` degrade to `None`. The `perihelion_q_au`/`eccentricity`/`inclination_deg`/`arg_perihelion_deg`/`node_deg` columns are NOT NULL in the schema — the fixture rows always carry them (they are the orbit); if a real row lacks one, the INSERT will raise, which is the desired loud failure.

- [ ] **Step 5: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_build_db.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add oracle/schema.sql oracle/oracle/build_db.py oracle/tests/test_build_db.py
git commit -m "feat(oracle): define reference.sqlite schema + builder"
```

---

### Task 7: Manifest generator

**Files:**
- Create: `oracle/oracle/manifest.py`
- Create: `oracle/tests/test_manifest.py`

**Interfaces:**
- Consumes: `BuildMeta` (Task 6).
- Produces: `write_manifest(sqlite_path: Path, out_path: Path, meta: BuildMeta, sqlite_url: str) -> dict` — writes `manifest.json` and returns the dict. Keys: `schema_version`, `generated_at`, `sqlite_url`, `sqlite_sha256`, `window_start`, `window_end`.

- [ ] **Step 1: Write the failing test**

```python
# oracle/tests/test_manifest.py
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from oracle.build_db import SCHEMA_VERSION, BuildMeta
from oracle.manifest import write_manifest


def _meta(now: str) -> BuildMeta:
    return BuildMeta(SCHEMA_VERSION, now, None, now, now, "de421.bsp")


def test_manifest_matches_file(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "reference.sqlite"
    sqlite_path.write_bytes(b"not-a-real-db-but-hashable")
    now = datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    manifest = write_manifest(
        sqlite_path, tmp_path / "manifest.json", _meta(now), "https://example/x.sqlite"
    )

    expected_sha = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
    assert manifest["sqlite_sha256"] == expected_sha
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["sqlite_url"] == "https://example/x.sqlite"
    on_disk = json.loads((tmp_path / "manifest.json").read_text())
    assert on_disk == manifest
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.manifest'`.

- [ ] **Step 3: Implement**

```python
# oracle/oracle/manifest.py
"""Emit manifest.json — the small sync point consumers poll."""

import hashlib
import json
from pathlib import Path

from oracle.build_db import BuildMeta


def write_manifest(
    sqlite_path: Path, out_path: Path, meta: BuildMeta, sqlite_url: str
) -> dict:
    digest = hashlib.sha256(sqlite_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": meta.schema_version,
        "generated_at": meta.generated_at,
        "sqlite_url": sqlite_url,
        "sqlite_sha256": digest,
        "window_start": meta.window_start,
        "window_end": meta.window_end,
    }
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_manifest.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add oracle/oracle/manifest.py oracle/tests/test_manifest.py
git commit -m "feat(oracle): write reference manifest with sha256"
```

---

### Task 8: End-to-end build entrypoint

**Files:**
- Create: `oracle/oracle/build.py`
- Create: `oracle/oracle/__main__.py`
- Create: `oracle/tests/test_build_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `build(out_dir: Path, start_utc: datetime, *, days: int = 60, sqlite_url: str, fetch: bool = True) -> tuple[Path, Path]` — runs fetch→load→compute→build_db→manifest, returns `(sqlite_path, manifest_path)`. `python -m oracle` calls it with defaults from env (`ORACLE_SQLITE_URL`, `ORACLE_OUT_DIR`).

- [ ] **Step 1: Write the failing integration test (offline: `fetch=False`)**

```python
# oracle/tests/test_build_pipeline.py
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build


def test_full_pipeline_offline(tmp_path: Path, monkeypatch) -> None:
    # force the fallback path by pointing the fetcher's dest at a copy,
    # and running with fetch=False (uses bundled fallback directly).
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    sqlite_path, manifest_path = build(
        tmp_path,
        start,
        days=3,
        sqlite_url="https://example/reference.sqlite",
        fetch=False,
    )
    assert sqlite_path.exists() and manifest_path.exists()
    con = sqlite3.connect(sqlite_path)
    try:
        (n,) = con.execute("SELECT COUNT(*) FROM comet_ephemeris").fetchone()
        assert n > 0
    finally:
        con.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd oracle && uv run pytest tests/test_build_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.build'`.

- [ ] **Step 3: Implement the orchestrator + CLI**

```python
# oracle/oracle/build.py
"""End-to-end reference build pipeline."""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import oracle
from oracle.build_db import SCHEMA_VERSION, BuildMeta, build_reference_db
from oracle.compute.ephemeris import compute_ephemeris
from oracle.manifest import write_manifest
from oracle.sources.comets import fetch_comet_els, load_comets


def build(
    out_dir: Path,
    start_utc: datetime,
    *,
    days: int = 60,
    sqlite_url: str,
    fetch: bool = True,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    els_path = out_dir / "CometEls.txt"
    if fetch:
        fetch_comet_els(els_path)
    else:
        shutil.copyfile(oracle.data_dir() / "CometEls.fallback.txt", els_path)

    comets = load_comets(els_path)
    kernel_path = oracle.data_dir() / "de421.bsp"
    rows = compute_ephemeris(comets, kernel_path, start_utc, days=days)

    now_iso = start_utc.isoformat().replace("+00:00", "Z")
    end_iso = (start_utc + timedelta(days=days)).isoformat().replace("+00:00", "Z")
    meta = BuildMeta(
        schema_version=SCHEMA_VERSION,
        generated_at=now_iso,
        mpc_epoch=None,
        window_start=now_iso,
        window_end=end_iso,
        skyfield_kernel="de421.bsp",
    )
    sqlite_path = build_reference_db(out_dir / "reference.sqlite", comets, rows, meta)
    manifest_path = out_dir / "manifest.json"
    write_manifest(sqlite_path, manifest_path, meta, sqlite_url)
    return sqlite_path, manifest_path
```

```python
# oracle/oracle/__main__.py
"""CLI: python -m oracle -> build reference.sqlite + manifest.json."""

import os
from datetime import datetime, timezone
from pathlib import Path

from oracle.build import build

if __name__ == "__main__":
    out_dir = Path(os.environ.get("ORACLE_OUT_DIR", "build_output"))
    sqlite_url = os.environ.get(
        "ORACLE_SQLITE_URL",
        "https://github.com/OWNER/REPO/releases/download/almanac-latest/reference.sqlite",
    )
    sqlite_path, manifest_path = build(
        out_dir, datetime.now(timezone.utc), sqlite_url=sqlite_url
    )
    print(f"built {sqlite_path} + {manifest_path}")
```

> `datetime.now(timezone.utc)` lives ONLY in `__main__` (the real CLI). Tests always pass an explicit `start_utc`, so they stay deterministic.

- [ ] **Step 4: Run to verify it passes**

Run: `cd oracle && uv run pytest tests/test_build_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `cd oracle && uv run pytest -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add oracle/oracle/build.py oracle/oracle/__main__.py oracle/tests/test_build_pipeline.py
git commit -m "feat(oracle): end-to-end build pipeline + CLI entrypoint"
```

---

### Task 9: GitHub Actions workflow + README (the consumer contract)

**Files:**
- Create: `.github/workflows/oracle.yml`
- Create: `oracle/README.md`

**Interfaces:**
- Consumes: `python -m oracle` (Task 8).
- Produces: a scheduled CI job publishing `reference.sqlite` + `manifest.json` as Release assets under the rolling tag `almanac-latest`; a README documenting the contract for `backend/` and `app/`.

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/oracle.yml
name: oracle-reference

on:
  schedule:
    - cron: "17 4 * * 1"   # weekly, Monday 04:17 UTC (best-effort)
  workflow_dispatch: {}
  push:
    paths:
      - "oracle/**"
      - ".github/workflows/oracle.yml"

permissions:
  contents: write   # required to update the Release asset

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Sync deps
        working-directory: oracle
        run: uv sync
      - name: Build reference artifact
        working-directory: oracle
        env:
          ORACLE_OUT_DIR: build_output
          ORACLE_SQLITE_URL: >-
            https://github.com/${{ github.repository }}/releases/download/almanac-latest/reference.sqlite
        run: uv run python -m oracle
      - name: Publish to rolling release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: almanac-latest
          files: |
            oracle/build_output/reference.sqlite
            oracle/build_output/manifest.json
```

- [ ] **Step 2: Write the README (contract doc)**

```markdown
# oracle/ — Astro-Brain reference data generator

Produces `reference.sqlite` (+ `manifest.json`) from a **GitHub Actions** cron
job. Runs **only in CI** — never on the Pi. `backend/` and `app/` consume the
published artifact; they never import from this package.

## What it does
Fetch MPC comet elements → skyfield ephemeris (daily apparent RA/Dec, of-date,
60-day rolling window) → SQLite → manifest.

## The contract (consumers read only this)
- `manifest.json`: `{ schema_version, generated_at, sqlite_url, sqlite_sha256,
  window_start, window_end }`. Poll it; download the SQLite only when
  `sqlite_sha256` changes. Refuse a `schema_version` newer than you support.
- `reference.sqlite`: tables `meta`, `comets`, `comet_ephemeris` (see
  `schema.sql`). **RA/Dec are apparent, of-date (JNow)** — consumers do only
  LST→alt/az. Daily samples → interpolate linearly.
- `predicted_mag` is an **estimate** (comet outbursts). Display as such; never
  a hard filter.

## Run locally
```bash
cd oracle && uv sync && uv run python -m oracle   # writes build_output/
```

## Publication
Release assets under the rolling tag `almanac-latest`. No binary is committed to
`main` (avoids history bloat).
```

- [ ] **Step 3: Verify the workflow file is valid YAML**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/oracle.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/oracle.yml oracle/README.md
git commit -m "ci(oracle): weekly reference build + publish, README contract"
```

- [ ] **Step 5: Manual CI verification (after push)**

Push the branch, then trigger `workflow_dispatch` from the Actions tab (or `gh workflow run oracle-reference`). Confirm: job green, and the `almanac-latest` release carries `reference.sqlite` + `manifest.json`. Download `manifest.json` and confirm `sqlite_sha256` matches the asset. This is the real-world proof the producer works end-to-end.

---

## Self-Review

**Spec coverage:** module structure (Tasks 1–2, 8–9) · MPC fetch + fallback (Task 4) · load/dedup (Task 3) · skyfield ephemeris, apparent of-date, predicted mag (Task 5) · `reference.sqlite` schema/contract (Task 6) · manifest/sync point (Task 7) · GitHub Actions cron + Release publish (Task 9) · README contract for consumers (Task 9). Consumer-side items (app/Pi sync, alt/az projection, notifs, GoTo resolution) are **deliberately out of scope** — separate plans.

**Placeholder scan:** no TBD/TODO; every code step carries full code; the only `OWNER/REPO` placeholder is in `__main__` and is overridden by `ORACLE_SQLITE_URL` in CI (documented).

**Type consistency:** `EphemRow` (Task 5) fields match the `INSERT` in Task 6 and the pipeline in Task 8. `BuildMeta`/`SCHEMA_VERSION` (Task 6) reused verbatim in Tasks 7–8. `build_reference_db`, `write_manifest`, `fetch_comet_els`, `load_comets`, `compute_ephemeris` signatures are consistent across their producing and consuming tasks.
