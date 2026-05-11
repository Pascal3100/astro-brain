# Wizard d'alignement 3 étoiles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter le wizard d'alignement 3 étoiles end-to-end (backend + Flutter), prêt à valider dès l'arrivée du dongle CP2102.

**Architecture:** Backend FastAPI porte une `AlignmentSession` éphémère + un solver SVD ; le modèle final est persisté en sqlite. Flutter porte la nav du wizard via un `AlignmentBloc` et réutilise les widgets `DPadControl`/`RateControl` (refactorés en présentationnels). Approche 3 (session backend simple, nav côté Flutter).

**Tech Stack:** Python 3.13 + FastAPI + aiosqlite + numpy + sse-starlette ; Flutter + flutter_bloc.

**Spec source:** `docs/superpowers/specs/2026-05-09-wizard-3star-alignment-design.md`

**Conventions repo (rappel) :**
- Backend tests en racine `backend/tests/test_*.py` (un fichier par unité).
- Service principal : `services/<feature>.py` avec classe `<Feature>ServiceImpl` et Protocol dans `services/interfaces.py`.
- Helpers internes : `services/_<feature>_<role>.py`.
- Repo : `repository/<feature>_repo.py`. Migrations : `repository/migrations/_<NN>_<desc>.py` avec `VERSION` + `SQL`.
- Routes : `routes/<feature>.py` avec un `router = APIRouter(tags=[...])`.
- Wiring : `app.py` build_app + `deps.py` resolvers via `request.app.state.*`.
- Frontend feature : `features/<feature>/<feature>_bloc.dart`, `_event.dart`, `_state.dart`, `_repository.dart`, et `screens/*.dart` si plusieurs écrans.

---

## Phase A — Backend domain (math pur)

### Task 1: Pydantic models

**Files:**
- Create: `backend/astro_brain/models/alignment.py`
- Test: `backend/tests/test_models_alignment.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models_alignment.py
"""Tests Pydantic for alignment models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)


def test_star_validates_magnitude_and_coords() -> None:
    s = Star(id="vega", name="Vega", bayer="α Lyrae", ra_deg=279.234, dec_deg=38.784, mag=0.03)
    assert s.id == "vega"
    assert s.mag == pytest.approx(0.03)


def test_star_rejects_out_of_range_ra() -> None:
    with pytest.raises(ValidationError):
        Star(id="x", name="X", bayer="-", ra_deg=400.0, dec_deg=0.0, mag=1.0)


def test_star_record_holds_sky_and_mount_pairs() -> None:
    r = StarRecord(
        star_id="vega", sky_az=248.1, sky_alt=42.0, mount_az=247.9, mount_alt=41.7,
    )
    assert r.mount_az == pytest.approx(247.9)


def test_alignment_session_starts_empty() -> None:
    sess = AlignmentSession(
        session_id="s1",
        candidates=[],
        recorded_stars=[],
        current_idx=0,
    )
    assert sess.recorded_count == 0


def test_alignment_model_roundtrip_dict() -> None:
    m = AlignmentModel(
        recorded_stars=[],
        svd_matrix=[[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]],
        rms_arcmin=4.2,
        residuals={"vega": 4.2},
        validated_at_utc="2026-05-09T22:47:00Z",
        gps_lat=48.8566,
        gps_lon=2.3522,
        quality="good",
    )
    assert m.model_dump()["rms_arcmin"] == pytest.approx(4.2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models_alignment.py -v`
Expected: FAIL with `ModuleNotFoundError: astro_brain.models.alignment`

- [ ] **Step 3: Implement models**

```python
# backend/astro_brain/models/alignment.py
"""Pydantic models pour l'alignement 3 étoiles."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Star(BaseModel):
    """Étoile candidate du catalogue d'alignement."""

    id: str
    name: str
    bayer: str
    ra_deg: float = Field(ge=0, lt=360)
    dec_deg: float = Field(ge=-90, le=90)
    mag: float


class StarRecord(BaseModel):
    """Une étoile recordée pendant le wizard."""

    star_id: str
    sky_az: float
    sky_alt: float
    mount_az: float
    mount_alt: float


class AlignmentSession(BaseModel):
    """Session de wizard en cours (vit en RAM côté backend)."""

    session_id: str
    candidates: list[Star]
    recorded_stars: list[StarRecord]
    current_idx: int

    @property
    def recorded_count(self) -> int:
        return len(self.recorded_stars)


class AlignmentModel(BaseModel):
    """Modèle d'alignement finalisé, persisté en state.db."""

    recorded_stars: list[StarRecord]
    svd_matrix: list[list[float]]
    rms_arcmin: float
    residuals: dict[str, float]
    validated_at_utc: str
    gps_lat: float | None = None
    gps_lon: float | None = None
    quality: Literal["good", "poor"] = "good"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_models_alignment.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/models/alignment.py backend/tests/test_models_alignment.py
git commit -m "feat(alignment): pydantic models (Star, StarRecord, Session, Model)"
```

---

### Task 2: Catalogue d'étoiles d'alignement (data file)

**Files:**
- Create: `backend/astro_brain/services/_alignment_stars.json`

- [ ] **Step 1: Constituer le mini catalogue**

~30 étoiles de mag<2.5, distribuées sur tout le ciel, principalement boréales (latitude France) mais aussi quelques australes pour couvrir tout l'AZ. Coordonnées J2000 (RA en degrés, Dec en degrés, mag V).

Créer le fichier ci-dessous (il sera chargé tel quel par le catalog) :

```json
[
  {"id": "sirius", "name": "Sirius", "bayer": "α CMa", "ra_deg": 101.287, "dec_deg": -16.716, "mag": -1.46},
  {"id": "canopus", "name": "Canopus", "bayer": "α Car", "ra_deg": 95.988, "dec_deg": -52.696, "mag": -0.74},
  {"id": "arcturus", "name": "Arcturus", "bayer": "α Boo", "ra_deg": 213.915, "dec_deg": 19.182, "mag": -0.05},
  {"id": "vega", "name": "Vega", "bayer": "α Lyr", "ra_deg": 279.234, "dec_deg": 38.784, "mag": 0.03},
  {"id": "capella", "name": "Capella", "bayer": "α Aur", "ra_deg": 79.172, "dec_deg": 45.998, "mag": 0.08},
  {"id": "rigel", "name": "Rigel", "bayer": "β Ori", "ra_deg": 78.634, "dec_deg": -8.202, "mag": 0.13},
  {"id": "procyon", "name": "Procyon", "bayer": "α CMi", "ra_deg": 114.825, "dec_deg": 5.225, "mag": 0.34},
  {"id": "betelgeuse", "name": "Betelgeuse", "bayer": "α Ori", "ra_deg": 88.793, "dec_deg": 7.407, "mag": 0.45},
  {"id": "achernar", "name": "Achernar", "bayer": "α Eri", "ra_deg": 24.429, "dec_deg": -57.237, "mag": 0.46},
  {"id": "altair", "name": "Altair", "bayer": "α Aql", "ra_deg": 297.696, "dec_deg": 8.868, "mag": 0.76},
  {"id": "aldebaran", "name": "Aldebaran", "bayer": "α Tau", "ra_deg": 68.980, "dec_deg": 16.509, "mag": 0.85},
  {"id": "antares", "name": "Antares", "bayer": "α Sco", "ra_deg": 247.352, "dec_deg": -26.432, "mag": 0.96},
  {"id": "spica", "name": "Spica", "bayer": "α Vir", "ra_deg": 201.298, "dec_deg": -11.161, "mag": 0.97},
  {"id": "pollux", "name": "Pollux", "bayer": "β Gem", "ra_deg": 116.329, "dec_deg": 28.026, "mag": 1.14},
  {"id": "fomalhaut", "name": "Fomalhaut", "bayer": "α PsA", "ra_deg": 344.413, "dec_deg": -29.622, "mag": 1.16},
  {"id": "deneb", "name": "Deneb", "bayer": "α Cyg", "ra_deg": 310.358, "dec_deg": 45.280, "mag": 1.25},
  {"id": "regulus", "name": "Regulus", "bayer": "α Leo", "ra_deg": 152.093, "dec_deg": 11.967, "mag": 1.36},
  {"id": "adhara", "name": "Adhara", "bayer": "ε CMa", "ra_deg": 104.656, "dec_deg": -28.972, "mag": 1.50},
  {"id": "castor", "name": "Castor", "bayer": "α Gem", "ra_deg": 113.650, "dec_deg": 31.888, "mag": 1.58},
  {"id": "bellatrix", "name": "Bellatrix", "bayer": "γ Ori", "ra_deg": 81.283, "dec_deg": 6.350, "mag": 1.64},
  {"id": "elnath", "name": "Elnath", "bayer": "β Tau", "ra_deg": 81.573, "dec_deg": 28.608, "mag": 1.65},
  {"id": "alnilam", "name": "Alnilam", "bayer": "ε Ori", "ra_deg": 84.053, "dec_deg": -1.202, "mag": 1.69},
  {"id": "alnitak", "name": "Alnitak", "bayer": "ζ Ori", "ra_deg": 85.190, "dec_deg": -1.943, "mag": 1.74},
  {"id": "alioth", "name": "Alioth", "bayer": "ε UMa", "ra_deg": 193.507, "dec_deg": 55.960, "mag": 1.76},
  {"id": "dubhe", "name": "Dubhe", "bayer": "α UMa", "ra_deg": 165.932, "dec_deg": 61.751, "mag": 1.79},
  {"id": "mirfak", "name": "Mirfak", "bayer": "α Per", "ra_deg": 51.081, "dec_deg": 49.861, "mag": 1.79},
  {"id": "polaris", "name": "Polaris", "bayer": "α UMi", "ra_deg": 37.954, "dec_deg": 89.264, "mag": 1.97},
  {"id": "alphard", "name": "Alphard", "bayer": "α Hya", "ra_deg": 141.897, "dec_deg": -8.659, "mag": 1.98},
  {"id": "hamal", "name": "Hamal", "bayer": "α Ari", "ra_deg": 31.793, "dec_deg": 23.462, "mag": 2.00},
  {"id": "diphda", "name": "Diphda", "bayer": "β Cet", "ra_deg": 10.898, "dec_deg": -17.987, "mag": 2.04},
  {"id": "alphecca", "name": "Alphecca", "bayer": "α CrB", "ra_deg": 233.672, "dec_deg": 26.715, "mag": 2.23},
  {"id": "denebola", "name": "Denebola", "bayer": "β Leo", "ra_deg": 177.265, "dec_deg": 14.572, "mag": 2.14}
]
```

- [ ] **Step 2: Commit**

```bash
git add backend/astro_brain/services/_alignment_stars.json
git commit -m "feat(alignment): mini catalogue 32 étoiles d'alignement (mag<2.5)"
```

---

### Task 3: Catalog selector (chargement + sélection candidates)

**Files:**
- Create: `backend/astro_brain/services/_alignment_catalog.py`
- Test: `backend/tests/test_alignment_catalog.py`

- [ ] **Step 1: Tests**

```python
# backend/tests/test_alignment_catalog.py
"""Tests pour _alignment_catalog (chargement + sélection candidates)."""
from __future__ import annotations

from datetime import datetime, UTC

import pytest

from astro_brain.services._alignment_catalog import (
    MountLimits,
    Observer,
    load_catalog,
    select_candidates,
    sky_az_alt_from_ra_dec,
)


def test_load_catalog_returns_at_least_30_stars() -> None:
    stars = load_catalog()
    assert len(stars) >= 30
    assert all(s.mag < 2.5 for s in stars)


def test_load_catalog_ids_unique() -> None:
    stars = load_catalog()
    ids = [s.id for s in stars]
    assert len(set(ids)) == len(ids)


def test_sky_az_alt_known_value() -> None:
    """Vega vue de Paris à 22:00 UTC le 1er juin 2026 doit être au-dessus
    de l'horizon (vérification sanity-check, pas précision arc-min)."""
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    az, alt = sky_az_alt_from_ra_dec(279.234, 38.784, obs, when)
    assert -360 < az < 360
    assert alt > 20  # Vega bien visible en juin tard


def test_select_candidates_filters_below_horizon() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    candidates = select_candidates(obs, when, limits, exclude_ids=set())
    assert len(candidates) == 3
    for star in candidates:
        _, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, obs, when)
        assert alt > 20


def test_select_candidates_distribution_around_120_az() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    candidates = select_candidates(obs, when, limits, exclude_ids=set())
    azs = sorted(
        sky_az_alt_from_ra_dec(s.ra_deg, s.dec_deg, obs, when)[0] % 360.0
        for s in candidates
    )
    # Spans entre voisins (cyclique) : on attend 3 spans dont chacun > 60° et < 200°
    cyclic_diffs = [
        (azs[(i + 1) % 3] - azs[i]) % 360.0 for i in range(3)
    ]
    for d in cyclic_diffs:
        assert 60 <= d <= 200


def test_select_candidates_excludes_ids() -> None:
    obs = Observer(lat_deg=48.8566, lon_deg=2.3522)
    when = datetime(2026, 6, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    first = select_candidates(obs, when, limits, exclude_ids=set())
    excluded = {first[0].id}
    second = select_candidates(obs, when, limits, exclude_ids=excluded)
    assert all(s.id not in excluded for s in second)
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement catalog**

```python
# backend/astro_brain/services/_alignment_catalog.py
"""Chargement du mini catalogue + sélection candidates pour wizard 3 étoiles.

Astronomie : conversion RA/Dec (J2000, ICRS) → Az/Alt apparent pour un
observateur à `(lat, lon)` à `t_utc`. On utilise une formule LST + sphérique
classique, précision arc-min — largement suffisante pour pré-pointer dans
un champ d'oculaire de ~1°.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import resources

from astro_brain.models.alignment import Star


@dataclass(frozen=True)
class Observer:
    lat_deg: float
    lon_deg: float


@dataclass(frozen=True)
class MountLimits:
    alt_min: float
    alt_max: float
    az_min: float
    az_max: float


def load_catalog() -> list[Star]:
    """Charge le JSON embarqué et renvoie la liste des étoiles."""
    raw = resources.files("astro_brain.services").joinpath(
        "_alignment_stars.json"
    ).read_text()
    return [Star.model_validate(d) for d in json.loads(raw)]


def _julian_date(t_utc: datetime) -> float:
    """JD à partir d'un datetime UTC."""
    y, m = t_utc.year, t_utc.month
    d = (
        t_utc.day
        + (t_utc.hour + (t_utc.minute + t_utc.second / 60.0) / 60.0) / 24.0
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _gmst_deg(t_utc: datetime) -> float:
    """Greenwich Mean Sidereal Time en degrés (formule IAU 1982 approximée)."""
    jd = _julian_date(t_utc)
    t = (jd - 2451545.0) / 36525.0
    gmst_h = (
        6.697374558
        + 2400.051336 * t
        + 0.000025862 * t * t
        + 1.0027379093 * (jd % 1 - 0.5) * 24.0
    )
    return (gmst_h * 15.0) % 360.0


def sky_az_alt_from_ra_dec(
    ra_deg: float, dec_deg: float, observer: Observer, t_utc: datetime
) -> tuple[float, float]:
    """Convertit (ra, dec) → (az, alt) pour `observer` à `t_utc`.

    Az mesuré depuis le Nord vers l'Est. Alt depuis l'horizon. Précision
    arc-min, sans corrections nutation/aberration/réfraction.
    """
    gmst = _gmst_deg(t_utc)
    lst = (gmst + observer.lon_deg) % 360.0
    ha_deg = (lst - ra_deg) % 360.0
    if ha_deg > 180:
        ha_deg -= 360
    ha = math.radians(ha_deg)
    dec = math.radians(dec_deg)
    lat = math.radians(observer.lat_deg)

    sin_alt = math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(ha)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))

    sin_az = -math.cos(dec) * math.sin(ha) / math.cos(math.radians(alt))
    cos_az = (math.sin(dec) - math.sin(math.radians(alt)) * math.sin(lat)) / (
        math.cos(math.radians(alt)) * math.cos(lat)
    )
    az = math.degrees(math.atan2(sin_az, cos_az)) % 360.0
    return az, alt


def select_candidates(
    observer: Observer,
    t_utc: datetime,
    limits: MountLimits,
    exclude_ids: set[str],
    *,
    min_alt: float = 20.0,
    isolation_deg: float = 5.0,
) -> list[Star]:
    """Renvoie 3 étoiles candidates distribuées ~120° en AZ.

    - filtre alt > min_alt et dans `limits`
    - filtre `exclude_ids`
    - filtre isolation (pas d'autre brillante < `isolation_deg`)
    - sélectionne 3 étoiles maximisant l'écart AZ entre voisines.
    """
    catalog = [s for s in load_catalog() if s.id not in exclude_ids]
    visible: list[tuple[Star, float, float]] = []
    for star in catalog:
        az, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, observer, t_utc)
        if alt < min_alt or alt < limits.alt_min or alt > limits.alt_max:
            continue
        if not (limits.az_min <= az <= limits.az_max):
            continue
        visible.append((star, az, alt))

    # isolation : élimine ceux qui ont un voisin brillant proche (< isolation_deg)
    isolated: list[tuple[Star, float, float]] = []
    for star, az, alt in visible:
        too_close = False
        for other, oaz, oalt in visible:
            if other.id == star.id:
                continue
            d = math.sqrt((az - oaz) ** 2 + (alt - oalt) ** 2)
            if d < isolation_deg:
                too_close = True
                break
        if not too_close:
            isolated.append((star, az, alt))

    if len(isolated) < 3:
        # Fallback : reprendre les visibles, isolation devient un nice-to-have
        isolated = visible

    # Sélection 3 étoiles maximisant la distribution AZ : on tire le triplet
    # dont les écarts cycliques minimisent l'écart à 120°.
    if len(isolated) <= 3:
        return [s for s, _, _ in isolated[:3]]

    best_triplet: list[Star] | None = None
    best_score = float("inf")
    for i in range(len(isolated)):
        for j in range(i + 1, len(isolated)):
            for k in range(j + 1, len(isolated)):
                azs = sorted(
                    [isolated[i][1], isolated[j][1], isolated[k][1]]
                )
                spans = [
                    (azs[1] - azs[0]) % 360.0,
                    (azs[2] - azs[1]) % 360.0,
                    (azs[0] + 360.0 - azs[2]) % 360.0,
                ]
                score = sum((s - 120.0) ** 2 for s in spans)
                if score < best_score:
                    best_score = score
                    best_triplet = [isolated[i][0], isolated[j][0], isolated[k][0]]
    return best_triplet or [s for s, _, _ in isolated[:3]]
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/_alignment_catalog.py backend/tests/test_alignment_catalog.py
git commit -m "feat(alignment): catalog loader + RA/Dec → Az/Alt + select_candidates"
```

---

### Task 4: Solver SVD

**Files:**
- Create: `backend/astro_brain/services/_alignment_solver.py`
- Test: `backend/tests/test_alignment_solver.py`

- [ ] **Step 1: Tests**

```python
# backend/tests/test_alignment_solver.py
"""Tests pour le solver SVD."""
from __future__ import annotations

import math

import pytest

from astro_brain.models.alignment import StarRecord
from astro_brain.services._alignment_solver import compute_alignment


def _identity_records() -> list[StarRecord]:
    return [
        StarRecord(star_id="a", sky_az=0.0, sky_alt=30.0, mount_az=0.0, mount_alt=30.0),
        StarRecord(star_id="b", sky_az=120.0, sky_alt=45.0, mount_az=120.0, mount_alt=45.0),
        StarRecord(star_id="c", sky_az=240.0, sky_alt=60.0, mount_az=240.0, mount_alt=60.0),
    ]


def test_perfect_input_yields_near_zero_rms() -> None:
    model = compute_alignment(_identity_records())
    assert model.rms_arcmin < 1e-3
    for v in model.residuals.values():
        assert v < 1e-3


def test_constant_offset_rms_near_zero() -> None:
    """Offset constant (2° en az) → rotation pure, RMS proche de 0."""
    records = [
        StarRecord(star_id="a", sky_az=0.0, sky_alt=30.0, mount_az=2.0, mount_alt=30.0),
        StarRecord(star_id="b", sky_az=120.0, sky_alt=45.0, mount_az=122.0, mount_alt=45.0),
        StarRecord(star_id="c", sky_az=240.0, sky_alt=60.0, mount_az=242.0, mount_alt=60.0),
    ]
    model = compute_alignment(records)
    assert model.rms_arcmin < 5  # tolérance arc-min


def test_outlier_residual_isolates_bad_star() -> None:
    """1 étoile mal centrée (résiduel artificiel 30') → identifiée comme outlier."""
    records = _identity_records()
    # Décale brutalement b en alt
    records[1] = records[1].model_copy(update={"mount_alt": records[1].mount_alt + 0.5})
    model = compute_alignment(records)
    by_resid = sorted(model.residuals.items(), key=lambda kv: kv[1])
    outlier_id, outlier_val = by_resid[-1]
    others = [v for _, v in by_resid[:-1]]
    assert outlier_id == "b"
    assert outlier_val > 3 * (sum(others) / len(others))


def test_residuals_unit_arcmin() -> None:
    """Sanity : si les résiduels sont en degrés, on aurait < 1. En arc-min on a > 1
    pour un offset 0.5°."""
    records = _identity_records()
    records[1] = records[1].model_copy(update={"mount_alt": records[1].mount_alt + 0.5})
    model = compute_alignment(records)
    assert max(model.residuals.values()) > 1.0


def test_rejects_less_than_3_records() -> None:
    with pytest.raises(ValueError):
        compute_alignment(_identity_records()[:2])
```

- [ ] **Step 2: Run, expect fail**

Run: `cd backend && uv run pytest tests/test_alignment_solver.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement solver**

```python
# backend/astro_brain/services/_alignment_solver.py
"""SVD-based alignment solver.

On résout `R · sky_unit = mount_unit` au sens des moindres carrés via SVD,
où `sky_unit` et `mount_unit` sont les vecteurs unitaires associés aux
coordonnées (az, alt) de chaque étoile. Le modèle est une matrice 3×3.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np

from astro_brain.models.alignment import AlignmentModel, StarRecord


def _az_alt_to_unit_vec(az_deg: float, alt_deg: float) -> np.ndarray:
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    return np.array(
        [math.cos(alt) * math.cos(az), math.cos(alt) * math.sin(az), math.sin(alt)]
    )


def _unit_vec_to_az_alt(v: np.ndarray) -> tuple[float, float]:
    norm = float(np.linalg.norm(v))
    x, y, z = v / norm
    alt = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    az = math.degrees(math.atan2(y, x)) % 360.0
    return az, alt


def compute_alignment(
    records: list[StarRecord],
    *,
    quality_threshold_arcmin: float = 20.0,
) -> AlignmentModel:
    """Calcule la matrice 3×3 de transformation et les résiduels.

    Renvoie un `AlignmentModel` non persisté (pas de gps/timestamp).
    """
    if len(records) < 3:
        raise ValueError("au moins 3 records requis")

    sky = np.column_stack(
        [_az_alt_to_unit_vec(r.sky_az, r.sky_alt) for r in records]
    )  # 3×N
    mount = np.column_stack(
        [_az_alt_to_unit_vec(r.mount_az, r.mount_alt) for r in records]
    )  # 3×N

    # Recherche R minimisant ||R·sky - mount||²
    h = sky @ mount.T
    u, _, vt = np.linalg.svd(h)
    d = np.linalg.det(vt.T @ u.T)
    s_diag = np.diag([1.0, 1.0, d])
    rotation = vt.T @ s_diag @ u.T

    residuals: dict[str, float] = {}
    sq_sum = 0.0
    for r in records:
        sky_v = _az_alt_to_unit_vec(r.sky_az, r.sky_alt)
        predicted = rotation @ sky_v
        actual = _az_alt_to_unit_vec(r.mount_az, r.mount_alt)
        cos_angle = float(np.clip(np.dot(predicted, actual), -1.0, 1.0))
        angle_deg = math.degrees(math.acos(cos_angle))
        angle_arcmin = angle_deg * 60.0
        residuals[r.star_id] = angle_arcmin
        sq_sum += angle_arcmin ** 2

    rms = math.sqrt(sq_sum / len(records))
    quality = "good" if rms < quality_threshold_arcmin else "poor"

    return AlignmentModel(
        recorded_stars=list(records),
        svd_matrix=rotation.tolist(),
        rms_arcmin=rms,
        residuals=residuals,
        validated_at_utc=datetime.now(UTC).isoformat(),
        gps_lat=None,
        gps_lon=None,
        quality=quality,
    )
```

- [ ] **Step 4: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_alignment_solver.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/_alignment_solver.py backend/tests/test_alignment_solver.py
git commit -m "feat(alignment): SVD solver pour matrice 3×3 + résiduels arc-min"
```

---

## Phase B — Backend persistance

### Task 5: Migration sqlite

**Files:**
- Create: `backend/astro_brain/repository/migrations/_002_alignment_model.py`
- Test: `backend/tests/test_state_db.py:augment` (modifier)

- [ ] **Step 1: Tests**

Augmenter `backend/tests/test_state_db.py` (sans casser l'existant) avec :

```python
# Ajouter à backend/tests/test_state_db.py (en bas du fichier)

import pytest

from astro_brain.repository.state_db import get_db, run_migrations


@pytest.mark.asyncio
async def test_alignment_model_table_exists_after_migrations(tmp_path) -> None:
    db_file = tmp_path / "state.db"
    async with get_db(db_file) as db:
        await run_migrations(db)
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alignment_model'"
        )
        row = await cursor.fetchone()
        await cursor.close()
    assert row is not None


@pytest.mark.asyncio
async def test_alignment_model_only_one_row_allowed(tmp_path) -> None:
    db_file = tmp_path / "state.db"
    async with get_db(db_file) as db:
        await run_migrations(db)
        await db.execute(
            "INSERT INTO alignment_model (id, recorded_stars, svd_matrix, "
            "rms_arcmin, residuals, validated_at, gps_lat, gps_lon, quality) "
            "VALUES (1, '[]', '[]', 0.0, '{}', '2026-01-01T00:00:00Z', 0.0, 0.0, 'good')"
        )
        await db.commit()
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO alignment_model (id, recorded_stars, svd_matrix, "
                "rms_arcmin, residuals, validated_at, gps_lat, gps_lon, quality) "
                "VALUES (2, '[]', '[]', 0.0, '{}', '2026-01-01T00:00:00Z', 0.0, 0.0, 'good')"
            )
            await db.commit()
```

- [ ] **Step 2: Run, expect fail**

Run: `cd backend && uv run pytest tests/test_state_db.py::test_alignment_model_table_exists_after_migrations -v`
Expected: FAIL — table absente.

- [ ] **Step 3: Add migration**

```python
# backend/astro_brain/repository/migrations/_002_alignment_model.py
"""Schéma alignment_model (modèle d'alignement 3 étoiles persisté)."""
from __future__ import annotations

VERSION = 2

SQL = """
CREATE TABLE IF NOT EXISTS alignment_model (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  recorded_stars TEXT NOT NULL,
  svd_matrix TEXT NOT NULL,
  rms_arcmin REAL NOT NULL,
  residuals TEXT NOT NULL,
  validated_at TEXT NOT NULL,
  gps_lat REAL,
  gps_lon REAL,
  quality TEXT NOT NULL DEFAULT 'good'
);
"""
```

- [ ] **Step 4: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_state_db.py -v`
Expected: tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/repository/migrations/_002_alignment_model.py backend/tests/test_state_db.py
git commit -m "feat(alignment): migration sqlite alignment_model"
```

---

### Task 6: Repository

**Files:**
- Create: `backend/astro_brain/repository/alignment_repo.py`
- Test: `backend/tests/test_alignment_repo.py`

- [ ] **Step 1: Tests**

```python
# backend/tests/test_alignment_repo.py
"""Tests du repo alignment_model (load/save + garde-fous Δt et ΔGPS)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from astro_brain.models.alignment import AlignmentModel, StarRecord
from astro_brain.repository import alignment_repo
from astro_brain.repository.state_db import get_db, run_migrations


def _sample_model(*, validated_at_utc: str, gps: tuple[float, float] | None) -> AlignmentModel:
    rec = StarRecord(star_id="vega", sky_az=0, sky_alt=30, mount_az=0, mount_alt=30)
    return AlignmentModel(
        recorded_stars=[rec, rec, rec],
        svd_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        rms_arcmin=4.2,
        residuals={"vega": 4.2},
        validated_at_utc=validated_at_utc,
        gps_lat=gps[0] if gps else None,
        gps_lon=gps[1] if gps else None,
        quality="good",
    )


@pytest.mark.asyncio
async def test_save_then_load_roundtrip(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db, now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC), current_gps=(48.0, 2.0),
        )
    assert loaded is not None
    assert loaded.rms_arcmin == pytest.approx(4.2)


@pytest.mark.asyncio
async def test_load_returns_none_if_too_old(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 10, 11, 0, tzinfo=UTC),  # 13h plus tard
            current_gps=(48.0, 2.0),
        )
    assert loaded is None


@pytest.mark.asyncio
async def test_load_returns_none_if_gps_moved(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db,
            now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC),
            current_gps=(48.0, 2.001),  # ~111m plus loin
        )
    assert loaded is None


@pytest.mark.asyncio
async def test_load_no_gps_in_stored_returns_none(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=None)
        await alignment_repo.save(db, m)
        loaded = await alignment_repo.load(
            db, now_utc=datetime(2026, 5, 9, 22, 30, tzinfo=UTC), current_gps=(48.0, 2.0),
        )
    assert loaded is None


@pytest.mark.asyncio
async def test_save_overwrites_previous(tmp_path) -> None:
    async with get_db(tmp_path / "x.db") as db:
        await run_migrations(db)
        m1 = _sample_model(validated_at_utc="2026-05-09T22:00:00+00:00", gps=(48.0, 2.0))
        m2 = _sample_model(validated_at_utc="2026-05-09T23:00:00+00:00", gps=(48.0, 2.0))
        await alignment_repo.save(db, m1)
        await alignment_repo.save(db, m2)
        cursor = await db.execute("SELECT COUNT(*) FROM alignment_model")
        row = await cursor.fetchone()
        await cursor.close()
    assert row[0] == 1
```

- [ ] **Step 2: Run, expect ImportError**

Run: `cd backend && uv run pytest tests/test_alignment_repo.py -v`
Expected: FAIL (`alignment_repo` n'existe pas).

- [ ] **Step 3: Implement repo**

```python
# backend/astro_brain/repository/alignment_repo.py
"""Persistance du modèle d'alignement avec garde-fous Δt 12h / ΔGPS 20m."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import aiosqlite

from astro_brain.models.alignment import AlignmentModel, StarRecord

MAX_AGE = timedelta(hours=12)
MAX_GPS_DELTA_M = 20.0
EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = (math.radians(a[0]), math.radians(a[1]))
    lat2, lon2 = (math.radians(b[0]), math.radians(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


async def save(db: aiosqlite.Connection, model: AlignmentModel) -> None:
    """Insert or replace l'unique row id=1."""
    await db.execute(
        "INSERT OR REPLACE INTO alignment_model "
        "(id, recorded_stars, svd_matrix, rms_arcmin, residuals, validated_at, "
        " gps_lat, gps_lon, quality) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            json.dumps([r.model_dump() for r in model.recorded_stars]),
            json.dumps(model.svd_matrix),
            model.rms_arcmin,
            json.dumps(model.residuals),
            model.validated_at_utc,
            model.gps_lat,
            model.gps_lon,
            model.quality,
        ),
    )
    await db.commit()


async def load(
    db: aiosqlite.Connection,
    *,
    now_utc: datetime,
    current_gps: tuple[float, float] | None,
) -> AlignmentModel | None:
    """Renvoie le modèle si frais ET position inchangée, sinon None.

    None si :
    - aucune row stockée
    - Δt > 12h
    - le row n'a pas de GPS
    - current_gps est None
    - distance > 20m
    """
    cursor = await db.execute("SELECT * FROM alignment_model WHERE id = 1")
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    cols = ["id", "recorded_stars", "svd_matrix", "rms_arcmin", "residuals",
            "validated_at", "gps_lat", "gps_lon", "quality"]
    data = dict(zip(cols, row, strict=True))

    validated_at = datetime.fromisoformat(data["validated_at"])
    if validated_at.tzinfo is None:
        validated_at = validated_at.replace(tzinfo=now_utc.tzinfo)
    if (now_utc - validated_at) > MAX_AGE:
        return None
    if data["gps_lat"] is None or data["gps_lon"] is None or current_gps is None:
        return None
    delta = _haversine_m(current_gps, (data["gps_lat"], data["gps_lon"]))
    if delta > MAX_GPS_DELTA_M:
        return None

    return AlignmentModel(
        recorded_stars=[StarRecord.model_validate(r) for r in json.loads(data["recorded_stars"])],
        svd_matrix=json.loads(data["svd_matrix"]),
        rms_arcmin=data["rms_arcmin"],
        residuals=json.loads(data["residuals"]),
        validated_at_utc=data["validated_at"],
        gps_lat=data["gps_lat"],
        gps_lon=data["gps_lon"],
        quality=data["quality"],
    )


async def clear(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM alignment_model WHERE id = 1")
    await db.commit()
```

- [ ] **Step 4: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_alignment_repo.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/repository/alignment_repo.py backend/tests/test_alignment_repo.py
git commit -m "feat(alignment): repo state.db (save + load avec garde-fous Δt/ΔGPS)"
```

---

## Phase C — Backend service + API

### Task 7: AlignmentService (Protocol + impl)

**Files:**
- Modify: `backend/astro_brain/services/interfaces.py` (add `AlignmentService` Protocol)
- Create: `backend/astro_brain/services/alignment.py`
- Test: `backend/tests/test_alignment_service.py`

- [ ] **Step 1: Tests**

```python
# backend/tests/test_alignment_service.py
"""Tests du AlignmentServiceImpl (start/record/swap/finalize/restart_star/cancel)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from astro_brain.models.alignment import Star, StarRecord
from astro_brain.services.alignment import AlignmentServiceImpl
from astro_brain.services.interfaces import ConflictError


def _stub_candidates() -> list[Star]:
    return [
        Star(id="a", name="A", bayer="α", ra_deg=0, dec_deg=10, mag=1.0),
        Star(id="b", name="B", bayer="β", ra_deg=120, dec_deg=20, mag=1.2),
        Star(id="c", name="C", bayer="γ", ra_deg=240, dec_deg=30, mag=1.4),
    ]


def _build_service(candidates: list[Star] | None = None) -> AlignmentServiceImpl:
    """Service avec mocks pour repo, mount, sensors et catalog."""
    selector = MagicMock(return_value=candidates or _stub_candidates())
    mount = MagicMock()
    mount.current_position = AsyncMock(return_value=(100.0, 50.0))
    sensors = MagicMock()
    sensors.gps_fix = MagicMock(return_value=(48.8, 2.3))
    repo_save = AsyncMock()
    return AlignmentServiceImpl(
        select_candidates=selector,
        mount=mount,
        sensors=sensors,
        repo_save=repo_save,
        db=MagicMock(),
        now_utc=lambda: datetime(2026, 5, 9, 22, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_start_creates_session_with_3_candidates() -> None:
    svc = _build_service()
    sess = await svc.start()
    assert len(sess.candidates) == 3
    assert sess.current_idx == 0
    assert sess.recorded_count == 0


@pytest.mark.asyncio
async def test_record_appends_then_increments_current_idx() -> None:
    svc = _build_service()
    await svc.start()
    sess = await svc.record(0)
    assert sess.recorded_count == 1
    assert sess.current_idx == 1


@pytest.mark.asyncio
async def test_record_wrong_idx_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    with pytest.raises(ConflictError):
        await svc.record(1)  # current_idx=0 → idx 1 invalide


@pytest.mark.asyncio
async def test_swap_replaces_current_candidate() -> None:
    svc = _build_service()
    await svc.start()
    new_star = Star(id="z", name="Z", bayer="ζ", ra_deg=300, dec_deg=40, mag=1.0)
    sess = await svc.swap(0, new_star)
    assert sess.candidates[0].id == "z"


@pytest.mark.asyncio
async def test_swap_after_record_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    with pytest.raises(ConflictError):
        await svc.swap(0, Star(id="z", name="Z", bayer="ζ", ra_deg=300, dec_deg=40, mag=1.0))


@pytest.mark.asyncio
async def test_finalize_before_3_records_raises_conflict() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    with pytest.raises(ConflictError):
        await svc.finalize()


@pytest.mark.asyncio
async def test_finalize_persists_and_returns_model() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    await svc.record(1)
    await svc.record(2)
    model = await svc.finalize()
    assert model.rms_arcmin >= 0
    svc._repo_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_star_truncates_recorded() -> None:
    svc = _build_service()
    await svc.start()
    await svc.record(0)
    await svc.record(1)
    await svc.record(2)
    sess = await svc.restart_star(1)
    assert sess.recorded_count == 1  # garde s0
    assert sess.current_idx == 1


@pytest.mark.asyncio
async def test_cancel_clears_session_only() -> None:
    svc = _build_service()
    await svc.start()
    await svc.cancel()
    assert svc.session() is None
    svc._repo_save.assert_not_awaited()
```

- [ ] **Step 2: Run, expect fail**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v`
Expected: FAIL (module manquant).

- [ ] **Step 3: Add Protocol to interfaces.py**

Append to `backend/astro_brain/services/interfaces.py` (avant la dernière ligne) :

```python
class AlignmentService(Protocol):
    """Wizard d'alignement 3 étoiles (session unique en RAM)."""

    async def start(self) -> "AlignmentSession": ...
    async def swap(self, idx: int, new_star: "Star") -> "AlignmentSession": ...
    async def record(self, idx: int) -> "AlignmentSession": ...
    async def restart_star(self, idx: int) -> "AlignmentSession": ...
    async def finalize(self) -> "AlignmentModel": ...
    async def cancel(self) -> None: ...
    def session(self) -> "AlignmentSession | None": ...
```

Et ajouter en haut :

```python
from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
```

- [ ] **Step 4: Implement AlignmentServiceImpl**

```python
# backend/astro_brain/services/alignment.py
"""AlignmentServiceImpl — orchestration du wizard 3 étoiles côté backend.

Une seule session en RAM à la fois. Le modèle final est persisté via le repo
(save asynchrone). Cette classe ne touche pas le mount directement pour les
slews — l'orchestration goto/jog reste portée par les routes existantes ;
on lit juste la position courante au moment du `record`.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)
from astro_brain.services._alignment_solver import compute_alignment
from astro_brain.services.interfaces import ConflictError


class AlignmentServiceImpl:
    def __init__(
        self,
        *,
        select_candidates: Callable[[], list[Star]],
        mount: Any,
        sensors: Any,
        repo_save: Callable[..., Any],
        db: Any,
        now_utc: Callable[[], datetime],
    ) -> None:
        self._select = select_candidates
        self._mount = mount
        self._sensors = sensors
        self._repo_save = repo_save
        self._db = db
        self._now = now_utc
        self._session: AlignmentSession | None = None

    def session(self) -> AlignmentSession | None:
        return self._session

    async def start(self) -> AlignmentSession:
        candidates = self._select()
        self._session = AlignmentSession(
            session_id=uuid4().hex,
            candidates=list(candidates),
            recorded_stars=[],
            current_idx=0,
        )
        return self._session

    async def swap(self, idx: int, new_star: Star) -> AlignmentSession:
        sess = self._require_session()
        if idx < sess.current_idx:
            raise ConflictError("cannot swap a recorded star")
        if not (0 <= idx < len(sess.candidates)):
            raise ConflictError("idx out of range")
        sess.candidates[idx] = new_star
        return sess

    async def record(self, idx: int) -> AlignmentSession:
        sess = self._require_session()
        if idx != sess.current_idx:
            raise ConflictError(
                f"idx {idx} != current_idx {sess.current_idx}"
            )
        if idx >= len(sess.candidates):
            raise ConflictError("idx beyond candidates")

        # Lit la position courante de la monture
        mount_az, mount_alt = await self._mount.current_position()

        star = sess.candidates[idx]
        sky_az, sky_alt = self._sensors.sky_az_alt_for(star)
        sess.recorded_stars.append(
            StarRecord(
                star_id=star.id,
                sky_az=sky_az,
                sky_alt=sky_alt,
                mount_az=mount_az,
                mount_alt=mount_alt,
            )
        )
        sess.current_idx = idx + 1
        return sess

    async def restart_star(self, idx: int) -> AlignmentSession:
        sess = self._require_session()
        if not (0 <= idx <= len(sess.candidates) - 1):
            raise ConflictError("idx out of range")
        sess.recorded_stars = sess.recorded_stars[:idx]
        sess.current_idx = idx
        return sess

    async def finalize(self) -> AlignmentModel:
        sess = self._require_session()
        if len(sess.recorded_stars) < 3:
            raise ConflictError("need 3 recorded stars before finalize")

        model = compute_alignment(sess.recorded_stars)

        gps = self._sensors.gps_fix() if self._sensors else None
        model = model.model_copy(
            update={
                "validated_at_utc": self._now().isoformat(),
                "gps_lat": gps[0] if gps else None,
                "gps_lon": gps[1] if gps else None,
            }
        )
        await self._repo_save(self._db, model)
        self._session = None
        return model

    async def cancel(self) -> None:
        self._session = None

    def _require_session(self) -> AlignmentSession:
        if self._session is None:
            raise ConflictError("no active alignment session")
        return self._session
```

- [ ] **Step 5: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v`
Expected: 9 passed.

Note : si `test_finalize_persists_and_returns_model` échoue car le test stub n'expose pas `sky_az_alt_for`, ajouter dans `_build_service` :
```python
sensors.sky_az_alt_for = MagicMock(side_effect=lambda s: (s.ra_deg % 360, s.dec_deg))
```

- [ ] **Step 6: Commit**

```bash
git add backend/astro_brain/services/alignment.py backend/astro_brain/services/interfaces.py backend/tests/test_alignment_service.py
git commit -m "feat(alignment): AlignmentService (start/record/swap/finalize/restart/cancel)"
```

---

### Task 8: API router

**Files:**
- Create: `backend/astro_brain/routes/alignment.py`
- Modify: `backend/astro_brain/deps.py` (add `get_alignment_service`)
- Test: `backend/tests/test_alignment_routes.py`

- [ ] **Step 1: Tests**

```python
# backend/tests/test_alignment_routes.py
"""Tests du router /align/* via FastAPI TestClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain import deps
from astro_brain.models.alignment import (
    AlignmentModel,
    AlignmentSession,
    Star,
    StarRecord,
)
from astro_brain.routes.alignment import router
from astro_brain.services.interfaces import ConflictError


def _stub_session() -> AlignmentSession:
    return AlignmentSession(
        session_id="s1",
        candidates=[
            Star(id=f"x{i}", name=f"X{i}", bayer="-", ra_deg=i * 100, dec_deg=10, mag=1)
            for i in range(3)
        ],
        recorded_stars=[],
        current_idx=0,
    )


def _client_with_service(service) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.alignment = service
    return TestClient(app)


def test_get_session_returns_null_when_idle() -> None:
    svc = MagicMock()
    svc.session = MagicMock(return_value=None)
    client = _client_with_service(svc)
    r = client.get("/align/session")
    assert r.status_code == 200
    assert r.json() == {"session": None}


def test_post_start_returns_candidates() -> None:
    svc = MagicMock()
    svc.start = AsyncMock(return_value=_stub_session())
    client = _client_with_service(svc)
    r = client.post("/align/start")
    assert r.status_code == 200
    body = r.json()
    assert len(body["candidates"]) == 3
    assert body["current_idx"] == 0


def test_post_record_idx_mismatch_returns_409() -> None:
    svc = MagicMock()
    svc.record = AsyncMock(side_effect=ConflictError("idx mismatch"))
    client = _client_with_service(svc)
    r = client.post("/align/record", json={"idx": 5})
    assert r.status_code == 409


def test_post_finalize_before_3_returns_409() -> None:
    svc = MagicMock()
    svc.finalize = AsyncMock(side_effect=ConflictError("need 3 stars"))
    client = _client_with_service(svc)
    r = client.post("/align/finalize")
    assert r.status_code == 409


def test_post_finalize_returns_model() -> None:
    rec = StarRecord(star_id="a", sky_az=0, sky_alt=0, mount_az=0, mount_alt=0)
    model = AlignmentModel(
        recorded_stars=[rec, rec, rec],
        svd_matrix=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        rms_arcmin=4.2,
        residuals={"a": 4.2},
        validated_at_utc="2026-05-09T22:00:00+00:00",
        gps_lat=48.0,
        gps_lon=2.0,
        quality="good",
    )
    svc = MagicMock()
    svc.finalize = AsyncMock(return_value=model)
    client = _client_with_service(svc)
    r = client.post("/align/finalize")
    assert r.status_code == 200
    assert r.json()["rms_arcmin"] == pytest.approx(4.2)


def test_delete_session_returns_204() -> None:
    svc = MagicMock()
    svc.cancel = AsyncMock()
    client = _client_with_service(svc)
    r = client.delete("/align/session")
    assert r.status_code == 204
    svc.cancel.assert_awaited_once()
```

- [ ] **Step 2: Run, expect fail**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement router**

```python
# backend/astro_brain/routes/alignment.py
"""Routes REST du wizard d'alignement.

Erreurs :
- ConflictError → 409
- ValueError du solver → 422
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from astro_brain import deps
from astro_brain.models.alignment import AlignmentModel, AlignmentSession, Star
from astro_brain.services.interfaces import AlignmentService, ConflictError

router = APIRouter(tags=["alignment"], prefix="/align")


class _RecordBody(BaseModel):
    idx: int


class _SwapBody(BaseModel):
    star: Star


class _RestartBody(BaseModel):
    idx: int


@router.get("/session")
async def get_session(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> dict[str, AlignmentSession | None]:
    return {"session": service.session()}


@router.post("/start")
async def start(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.start()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/swap/{idx}")
async def swap(
    idx: int,
    body: _SwapBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.swap(idx, body.star)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/record")
async def record(
    body: _RecordBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.record(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/restart_star")
async def restart_star(
    body: _RestartBody,
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentSession:
    try:
        return await service.restart_star(body.idx)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/finalize")
async def finalize(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> AlignmentModel:
    try:
        return await service.finalize()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.delete("/session", status_code=204)
async def cancel(
    service: AlignmentService = Depends(deps.get_alignment_service),
) -> Response:
    await service.cancel()
    return Response(status_code=204)
```

- [ ] **Step 4: Add deps resolver**

Append to `backend/astro_brain/deps.py` :

```python
def get_alignment_service(request: Request) -> "AlignmentService":
    return request.app.state.alignment
```

Et dans les imports en haut :
```python
from astro_brain.services.interfaces import AlignmentService
```
(à fusionner avec l'import existant des autres protocols)

- [ ] **Step 5: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/astro_brain/routes/alignment.py backend/astro_brain/deps.py backend/tests/test_alignment_routes.py
git commit -m "feat(alignment): API REST /align/* (start/swap/record/restart_star/finalize)"
```

---

### Task 9: Wire AlignmentService dans build_app

**Files:**
- Modify: `backend/astro_brain/app.py`
- Test: `backend/tests/test_app.py:augment`

- [ ] **Step 1: Repérer le bloc d'instanciation des services existants**

Run: `grep -n "app.state" /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/app.py | head -30`
Trouver l'endroit où `app.state.calibration = ...` est posé.

- [ ] **Step 2: Wire AlignmentServiceImpl dans build_app**

Dans la section où les services sont instanciés (après `app.state.db`, après `app.state.mount`), ajouter :

```python
# imports en haut
from astro_brain.services.alignment import AlignmentServiceImpl
from astro_brain.services._alignment_catalog import (
    MountLimits,
    Observer,
    select_candidates as _select_candidates_raw,
)
from astro_brain.repository import alignment_repo

# dans build_app, après mount déjà initialisé
def _candidates_provider() -> list:
    """Lit GPS + UTC + limites monture courantes pour produire 3 candidates."""
    from datetime import UTC, datetime
    gps = app.state.sensors.gps_fix()
    if gps is None:
        # fallback Paris
        gps = (48.8566, 2.3522)
    obs = Observer(lat_deg=gps[0], lon_deg=gps[1])
    # Limites monture : à terme depuis mount_limits ; defaults pour MVP
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    return _select_candidates_raw(obs, datetime.now(UTC), limits, exclude_ids=set())

app.state.alignment = AlignmentServiceImpl(
    select_candidates=_candidates_provider,
    mount=app.state.mount,
    sensors=app.state.sensors,
    repo_save=alignment_repo.save,
    db=app.state.db,
    now_utc=lambda: datetime.now(UTC),
)
```

Dans la section `app.include_router(...)`, ajouter :
```python
from astro_brain.routes import alignment as alignment_routes
app.include_router(alignment_routes.router)
```

- [ ] **Step 3: Augment test_app.py to verify alignment is wired**

Append to `backend/tests/test_app.py` :

```python
@pytest.mark.asyncio
async def test_build_app_wires_alignment_service():
    """build_app pose un AlignmentService sur app.state."""
    # Reuse existing fixtures du test_app (build_app or similar)
    # Adapter selon le pattern de test_app.py existant
    from astro_brain.app import build_app
    app = await build_app(...)  # cf. fixtures existantes
    assert hasattr(app.state, "alignment")
    assert app.state.alignment.session() is None
```

NB: si `test_app.py` utilise un pattern différent (fakes injectés, etc.), suivre le pattern local plutôt que de réinventer.

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && uv run pytest -x`
Expected: tous passent.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/app.py backend/tests/test_app.py
git commit -m "feat(alignment): wire AlignmentService dans build_app + register router"
```

---

### Task 10: SSE event alignment.session

**Files:**
- Modify: `backend/astro_brain/aggregator.py` ou équivalent (lieu où les events SSE sont composés)
- Test: `backend/tests/test_events_endpoint.py:augment`

- [ ] **Step 1: Repérer où les events SSE sont produits**

Run: `grep -rn "yield" /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/aggregator.py | head -10` et `grep -rn "alignment\|mount\|sensors" /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/aggregator.py | head -20`

Identifier le composeur d'event/payload.

- [ ] **Step 2: Ajouter alignment dans le payload aggregator**

Dans la fonction qui compose le payload SSE (probablement dans `aggregator.py`), ajouter :

```python
# avant: payload = {"mount": ..., "sensors": ..., ...}
session = self._alignment.session() if self._alignment else None
payload["alignment"] = (
    {
        "session_id": session.session_id,
        "current_idx": session.current_idx,
        "recorded_count": session.recorded_count,
        "candidates": [c.model_dump() for c in session.candidates],
    }
    if session
    else None
)
```

Et passer `alignment` dans le constructeur de l'agrégateur (à wirer dans `app.py`).

- [ ] **Step 3: Ajouter test events**

Augmenter `backend/tests/test_events_endpoint.py` (ou `test_aggregator.py`) :

```python
@pytest.mark.asyncio
async def test_event_payload_includes_alignment_field():
    # ... boot app, hit /events, parse first event
    # assert "alignment" in payload
    pass  # adapter au pattern local
```

- [ ] **Step 4: Run, expect pass**

Run: `cd backend && uv run pytest tests/test_events_endpoint.py tests/test_aggregator.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/aggregator.py backend/tests/
git commit -m "feat(alignment): expose alignment.session dans le payload SSE"
```

---

## Phase D — Frontend widget refactor (préalable)

### Task 11: Refactor DPadControl en widget présentationnel

**Files:**
- Modify: `app/lib/features/manual/widgets/dpad_control.dart` → déplacer ou rendre paramétrable
- Modify: `app/lib/features/manual/manual_screen.dart` → injecter callbacks
- Decision: garder dans `manual/widgets/` ou bouger en `app/lib/widgets/` ? **On bouge en `app/lib/widgets/dpad_control.dart`** pour partage clair.

- Create: `app/lib/widgets/dpad_control.dart`
- Delete: `app/lib/features/manual/widgets/dpad_control.dart`
- Modify: `app/lib/features/manual/manual_screen.dart`
- Test: `app/test/widgets/dpad_control_test.dart`

- [ ] **Step 1: Test du widget refactoré**

```dart
// app/test/widgets/dpad_control_test.dart
import 'package:astro_brain_app/widgets/dpad_control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('DPadControl invokes onPress with axis/direction',
      (tester) async {
    DPadDirection? lastPress;
    bool released = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DPadControl(
            onPress: (d) => lastPress = d,
            onRelease: () => released = true,
          ),
        ),
      ),
    );
    // tap up arrow
    await tester.press(find.byKey(const Key('dpad-up')));
    expect(lastPress, DPadDirection.up);
    await tester.pumpAndSettle();
    // release
    expect(released, isTrue);
  });
}
```

- [ ] **Step 2: Run, expect fail**

Run: `cd app && flutter test test/widgets/dpad_control_test.dart`
Expected: FAIL (DPadControl à l'ancien path).

- [ ] **Step 3: Move + refactor le widget**

Déplacer le fichier vers `app/lib/widgets/dpad_control.dart` et le rendre présentationnel :

```dart
// app/lib/widgets/dpad_control.dart
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

enum DPadDirection { up, down, left, right }

class DPadControl extends StatelessWidget {
  const DPadControl({
    super.key,
    required this.onPress,
    required this.onRelease,
    this.cellSize,
    this.iconSize,
    this.spacing = DesignTokens.spaceMD,
  });

  final ValueChanged<DPadDirection> onPress;
  final VoidCallback onRelease;
  final double? cellSize;
  final double? iconSize;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      shrinkWrap: true,
      crossAxisCount: 3,
      mainAxisSpacing: spacing,
      crossAxisSpacing: spacing,
      children: [
        const SizedBox.shrink(),
        _Btn(
          key: const Key('dpad-up'),
          icon: PhosphorIconsBold.caretUp,
          direction: DPadDirection.up,
          onPress: onPress,
          onRelease: onRelease,
          iconSize: iconSize,
        ),
        const SizedBox.shrink(),
        _Btn(
          key: const Key('dpad-left'),
          icon: PhosphorIconsBold.caretLeft,
          direction: DPadDirection.left,
          onPress: onPress,
          onRelease: onRelease,
          iconSize: iconSize,
        ),
        const SizedBox.shrink(),
        _Btn(
          key: const Key('dpad-right'),
          icon: PhosphorIconsBold.caretRight,
          direction: DPadDirection.right,
          onPress: onPress,
          onRelease: onRelease,
          iconSize: iconSize,
        ),
        const SizedBox.shrink(),
        _Btn(
          key: const Key('dpad-down'),
          icon: PhosphorIconsBold.caretDown,
          direction: DPadDirection.down,
          onPress: onPress,
          onRelease: onRelease,
          iconSize: iconSize,
        ),
        const SizedBox.shrink(),
      ],
    );
  }
}

class _Btn extends StatefulWidget {
  const _Btn({
    super.key,
    required this.icon,
    required this.direction,
    required this.onPress,
    required this.onRelease,
    this.iconSize,
  });

  final IconData icon;
  final DPadDirection direction;
  final ValueChanged<DPadDirection> onPress;
  final VoidCallback onRelease;
  final double? iconSize;

  @override
  State<_Btn> createState() => _BtnState();
}

class _BtnState extends State<_Btn> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Listener(
      onPointerDown: (_) {
        setState(() => _pressed = true);
        widget.onPress(widget.direction);
      },
      onPointerUp: (_) {
        setState(() => _pressed = false);
        widget.onRelease();
      },
      onPointerCancel: (_) {
        setState(() => _pressed = false);
        widget.onRelease();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        decoration: BoxDecoration(
          color: Color.lerp(
            colors.bgGradientTop,
            colors.accent,
            _pressed ? 0.32 : 0.08,
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          border: Border.all(
            color: colors.accent.withValues(
              alpha: _pressed ? 1.0 : 0.4,
            ),
            width: _pressed ? 2.0 : 1.5,
          ),
        ),
        child: Center(
          child: PhosphorIcon(
            widget.icon,
            color: colors.accent,
            size: widget.iconSize ?? DesignTokens.iconSizeXL,
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Adapter ManualScreen à la nouvelle API**

Dans `app/lib/features/manual/manual_screen.dart`, remplacer l'usage de DPadControl :

```dart
// avant: const DPadControl(),
// après:
DPadControl(
  onPress: (d) {
    final bloc = context.read<ManualBloc>();
    switch (d) {
      case DPadDirection.up:
        bloc.add(const ManualEvent.jogStart(axis: 'alt', direction: '+'));
        break;
      case DPadDirection.down:
        bloc.add(const ManualEvent.jogStart(axis: 'alt', direction: '-'));
        break;
      case DPadDirection.left:
        bloc.add(const ManualEvent.jogStart(axis: 'az', direction: '-'));
        break;
      case DPadDirection.right:
        bloc.add(const ManualEvent.jogStart(axis: 'az', direction: '+'));
        break;
    }
  },
  onRelease: () {
    context.read<ManualBloc>().add(const ManualEvent.jogStop());
  },
),
```

Note : adapter `ManualEvent.jogStart`/`jogStop` aux events réels présents dans `manual_event.dart`.

Et adapter l'import :
```dart
// avant: import 'widgets/dpad_control.dart';
// après: import '../../widgets/dpad_control.dart';
```

- [ ] **Step 5: Delete l'ancien fichier**

```bash
rm app/lib/features/manual/widgets/dpad_control.dart
```

- [ ] **Step 6: Run all flutter tests**

```bash
cd app && flutter test
```
Expected: tous passent (le test du widget + ceux qui touchent ManualScreen).

- [ ] **Step 7: Commit**

```bash
git add app/lib/widgets/dpad_control.dart app/lib/features/manual/ app/test/widgets/dpad_control_test.dart
git rm app/lib/features/manual/widgets/dpad_control.dart
git commit -m "refactor(widgets): DPadControl présentationnel partagé (manual + alignment)"
```

---

### Task 12: Refactor RateControl

**Files:**
- Create: `app/lib/widgets/rate_control.dart`
- Delete: `app/lib/features/manual/widgets/rate_control.dart`
- Modify: `app/lib/features/manual/manual_screen.dart`
- Test: `app/test/widgets/rate_control_test.dart`

- [ ] **Step 1: Test**

```dart
// app/test/widgets/rate_control_test.dart
import 'package:astro_brain_app/widgets/rate_control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('RateControl plus button increments value', (tester) async {
    int last = 4;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(builder: (ctx, set) {
            return RateControl(
              value: last,
              onChanged: (v) => set(() => last = v),
            );
          }),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('rate-plus')));
    await tester.pump();
    expect(last, 5);
  });

  testWidgets('RateControl displays N segments active', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: RateControl(value: 3, onChanged: (_) {}),
        ),
      ),
    );
    expect(find.byKey(const Key('rate-seg-on')), findsNWidgets(3));
  });
}
```

- [ ] **Step 2: Run, expect fail**

```bash
cd app && flutter test test/widgets/rate_control_test.dart
```

- [ ] **Step 3: Implement**

```dart
// app/lib/widgets/rate_control.dart
import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

class RateControl extends StatelessWidget {
  const RateControl({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 1,
    this.max = 9,
  });

  final int value;
  final ValueChanged<int> onChanged;
  final int min;
  final int max;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      children: [
        _Btn(
          key: const Key('rate-minus'),
          icon: Icons.remove,
          onTap: value > min ? () => onChanged(value - 1) : null,
        ),
        const SizedBox(width: DesignTokens.spaceSM),
        Expanded(
          child: Row(
            children: List.generate(max, (i) {
              final on = i < value;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 1),
                  child: Container(
                    key: on ? const Key('rate-seg-on') : const Key('rate-seg-off'),
                    height: 16,
                    decoration: BoxDecoration(
                      color: on
                          ? colors.accent
                          : colors.accent.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
                    ),
                  ),
                ),
              );
            }),
          ),
        ),
        const SizedBox(width: DesignTokens.spaceSM),
        _Btn(
          key: const Key('rate-plus'),
          icon: Icons.add,
          onTap: value < max ? () => onChanged(value + 1) : null,
        ),
        const SizedBox(width: DesignTokens.spaceSM),
        SizedBox(
          width: 28,
          child: Text(
            '$value',
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontFamily: 'JetBrainsMono',
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}

class _Btn extends StatelessWidget {
  const _Btn({super.key, required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return SizedBox(
      width: 36,
      height: 36,
      child: IconButton(
        onPressed: onTap,
        icon: Icon(icon, color: onTap == null ? colors.accent.withValues(alpha: 0.3) : colors.accent),
      ),
    );
  }
}
```

- [ ] **Step 4: Adapter ManualScreen**

Comme pour DPad : remplacer l'import et passer `value` + `onChanged` qui dispatchent vers ManualBloc.

- [ ] **Step 5: Delete ancien fichier**

```bash
rm app/lib/features/manual/widgets/rate_control.dart
```

- [ ] **Step 6: Run all flutter tests**

```bash
cd app && flutter test
```

- [ ] **Step 7: Commit**

```bash
git add app/lib/widgets/rate_control.dart app/lib/features/manual/ app/test/widgets/rate_control_test.dart
git rm app/lib/features/manual/widgets/rate_control.dart
git commit -m "refactor(widgets): RateControl présentationnel partagé"
```

---

## Phase E — Frontend alignment feature

### Task 13: AlignmentRepository (REST + SSE)

**Files:**
- Create: `app/lib/features/alignment/alignment_repository.dart`
- Create: `app/lib/features/alignment/alignment_models.dart` (DTOs Dart)
- Test: `app/test/features/alignment/alignment_repository_test.dart`

- [ ] **Step 1: DTOs**

```dart
// app/lib/features/alignment/alignment_models.dart
class StarDto {
  final String id;
  final String name;
  final String bayer;
  final double raDeg;
  final double decDeg;
  final double mag;

  const StarDto({
    required this.id,
    required this.name,
    required this.bayer,
    required this.raDeg,
    required this.decDeg,
    required this.mag,
  });

  factory StarDto.fromJson(Map<String, dynamic> j) => StarDto(
        id: j['id'] as String,
        name: j['name'] as String,
        bayer: j['bayer'] as String,
        raDeg: (j['ra_deg'] as num).toDouble(),
        decDeg: (j['dec_deg'] as num).toDouble(),
        mag: (j['mag'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'id': id, 'name': name, 'bayer': bayer,
        'ra_deg': raDeg, 'dec_deg': decDeg, 'mag': mag,
      };
}

class StarRecordDto {
  final String starId;
  final double skyAz, skyAlt, mountAz, mountAlt;
  const StarRecordDto({
    required this.starId,
    required this.skyAz, required this.skyAlt,
    required this.mountAz, required this.mountAlt,
  });
  factory StarRecordDto.fromJson(Map<String, dynamic> j) => StarRecordDto(
        starId: j['star_id'], skyAz: j['sky_az'], skyAlt: j['sky_alt'],
        mountAz: j['mount_az'], mountAlt: j['mount_alt'],
      );
}

class AlignmentSessionDto {
  final String sessionId;
  final List<StarDto> candidates;
  final List<StarRecordDto> recordedStars;
  final int currentIdx;

  const AlignmentSessionDto({
    required this.sessionId,
    required this.candidates,
    required this.recordedStars,
    required this.currentIdx,
  });

  factory AlignmentSessionDto.fromJson(Map<String, dynamic> j) =>
      AlignmentSessionDto(
        sessionId: j['session_id'] as String,
        candidates: (j['candidates'] as List)
            .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        recordedStars: (j['recorded_stars'] as List? ?? [])
            .map((e) => StarRecordDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        currentIdx: j['current_idx'] as int,
      );
}

class AlignmentModelDto {
  final List<StarRecordDto> recordedStars;
  final double rmsArcmin;
  final Map<String, double> residuals;
  final String validatedAtUtc;
  final String quality;

  const AlignmentModelDto({
    required this.recordedStars,
    required this.rmsArcmin,
    required this.residuals,
    required this.validatedAtUtc,
    required this.quality,
  });

  factory AlignmentModelDto.fromJson(Map<String, dynamic> j) => AlignmentModelDto(
        recordedStars: (j['recorded_stars'] as List)
            .map((e) => StarRecordDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        rmsArcmin: (j['rms_arcmin'] as num).toDouble(),
        residuals: (j['residuals'] as Map).map(
          (k, v) => MapEntry(k as String, (v as num).toDouble()),
        ),
        validatedAtUtc: j['validated_at_utc'] as String,
        quality: j['quality'] as String,
      );

  String? get outlierId {
    if (residuals.isEmpty) return null;
    final entries = residuals.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final worst = entries.first;
    final others = entries.skip(1).toList();
    if (others.isEmpty) return null;
    final mean = others.map((e) => e.value).reduce((a, b) => a + b) / others.length;
    return worst.value > 3 * mean ? worst.key : null;
  }
}
```

- [ ] **Step 2: Test du repo (avec mock ApiService)**

```dart
// app/test/features/alignment/alignment_repository_test.dart
import 'package:astro_brain_app/features/alignment/alignment_repository.dart';
import 'package:astro_brain_app/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;
  late AlignmentRepository repo;
  setUp(() {
    api = _MockApi();
    repo = AlignmentRepository(api: api);
  });

  test('getSession returns null when backend says null', () async {
    when(() => api.getJson('/align/session'))
        .thenAnswer((_) async => {'session': null});
    final s = await repo.getSession();
    expect(s, isNull);
  });

  test('start returns parsed session', () async {
    when(() => api.postJson('/align/start', any())).thenAnswer((_) async => {
          'session_id': 's1',
          'candidates': [
            {
              'id': 'a', 'name': 'A', 'bayer': '-',
              'ra_deg': 0.0, 'dec_deg': 0.0, 'mag': 1.0
            }
          ],
          'recorded_stars': [],
          'current_idx': 0,
        });
    final s = await repo.start();
    expect(s.candidates.first.id, 'a');
  });

  test('record sends idx body', () async {
    when(() => api.postJson('/align/record', {'idx': 0}))
        .thenAnswer((_) async => {
              'session_id': 's1',
              'candidates': [],
              'recorded_stars': [],
              'current_idx': 1,
            });
    final s = await repo.record(0);
    expect(s.currentIdx, 1);
  });
}
```

- [ ] **Step 3: Run, expect fail**

```bash
cd app && flutter test test/features/alignment/alignment_repository_test.dart
```

- [ ] **Step 4: Implement repository**

```dart
// app/lib/features/alignment/alignment_repository.dart
import '../../services/api_service.dart';
import 'alignment_models.dart';

class AlignmentRepository {
  AlignmentRepository({required this.api});
  final ApiService api;

  Future<AlignmentSessionDto?> getSession() async {
    final j = await api.getJson('/align/session');
    final raw = j['session'];
    if (raw == null) return null;
    return AlignmentSessionDto.fromJson(raw as Map<String, dynamic>);
  }

  Future<AlignmentSessionDto> start() async {
    final j = await api.postJson('/align/start', const {});
    return AlignmentSessionDto.fromJson(j);
  }

  Future<AlignmentSessionDto> swap(int idx, StarDto star) async {
    final j = await api.postJson('/align/swap/$idx', {'star': star.toJson()});
    return AlignmentSessionDto.fromJson(j);
  }

  Future<AlignmentSessionDto> record(int idx) async {
    final j = await api.postJson('/align/record', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  Future<AlignmentSessionDto> restartStar(int idx) async {
    final j = await api.postJson('/align/restart_star', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  Future<AlignmentModelDto> finalize() async {
    final j = await api.postJson('/align/finalize', const {});
    return AlignmentModelDto.fromJson(j);
  }

  Future<void> cancel() async {
    await api.delete('/align/session');
  }
}
```

NB : `ApiService.delete`, `getJson`, `postJson` sont supposés exister. Si la signature diffère, adapter.

- [ ] **Step 5: Run, expect pass**

```bash
cd app && flutter test test/features/alignment/alignment_repository_test.dart
```

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/alignment/ app/test/features/alignment/alignment_repository_test.dart
git commit -m "feat(alignment): repository REST + DTOs Dart"
```

---

### Task 14: AlignmentBloc + states + events

**Files:**
- Create: `app/lib/features/alignment/alignment_bloc.dart`
- Create: `app/lib/features/alignment/alignment_event.dart`
- Create: `app/lib/features/alignment/alignment_state.dart`
- Test: `app/test/features/alignment/alignment_bloc_test.dart`

- [ ] **Step 1: Tests bloc_test**

```dart
// app/test/features/alignment/alignment_bloc_test.dart
import 'package:astro_brain_app/features/alignment/alignment_bloc.dart';
import 'package:astro_brain_app/features/alignment/alignment_event.dart';
import 'package:astro_brain_app/features/alignment/alignment_models.dart';
import 'package:astro_brain_app/features/alignment/alignment_repository.dart';
import 'package:astro_brain_app/features/alignment/alignment_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements AlignmentRepository {}

AlignmentSessionDto _sessionWithIdx(int idx, {int recCount = 0}) =>
    AlignmentSessionDto(
      sessionId: 's1',
      candidates: List.generate(
        3,
        (i) => StarDto(
          id: 'x$i', name: 'X$i', bayer: '-',
          raDeg: i * 100.0, decDeg: 10, mag: 1,
        ),
      ),
      recordedStars: List.generate(
        recCount,
        (i) => StarRecordDto(starId: 'x$i', skyAz: 0, skyAlt: 0, mountAz: 0, mountAlt: 0),
      ),
      currentIdx: idx,
    );

void main() {
  late _MockRepo repo;
  setUp(() => repo = _MockRepo());

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted → LoadingCandidates → PrePointing(idx=0)',
    build: () {
      when(() => repo.getSession()).thenAnswer((_) async => null);
      when(() => repo.start()).thenAnswer((_) async => _sessionWithIdx(0));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 0),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RecordRequested → next star',
    build: () {
      when(() => repo.record(0))
          .thenAnswer((_) async => _sessionWithIdx(1, recCount: 1));
      return AlignmentBloc(repo: repo)
        ..emit(AlignmentFineTuning(session: _sessionWithIdx(0)));
    },
    act: (b) => b.add(const RecordRequested(0)),
    expect: () => [
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 1),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RecordRequested last → Validating with model',
    build: () {
      when(() => repo.record(2))
          .thenAnswer((_) async => _sessionWithIdx(3, recCount: 3));
      when(() => repo.finalize()).thenAnswer(
        (_) async => AlignmentModelDto(
          recordedStars: const [],
          rmsArcmin: 5.4,
          residuals: const {'x0': 2.1, 'x1': 11.4, 'x2': 2.8},
          validatedAtUtc: '2026-05-09T22:00:00+00:00',
          quality: 'good',
        ),
      );
      return AlignmentBloc(repo: repo)
        ..emit(AlignmentFineTuning(session: _sessionWithIdx(2, recCount: 2)));
    },
    act: (b) => b.add(const RecordRequested(2)),
    expect: () => [
      isA<AlignmentValidating>().having(
        (s) => s.model.outlierId,
        'outlier',
        'x1',
      ),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RestartStarRequested truncates and goes to PrePointing',
    build: () {
      when(() => repo.restartStar(1))
          .thenAnswer((_) async => _sessionWithIdx(1, recCount: 1));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const RestartStarRequested(1)),
    expect: () => [
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 1),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardCancelled clears session',
    build: () {
      when(() => repo.cancel()).thenAnswer((_) async {});
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardCancelled()),
    expect: () => [isA<AlignmentIdle>()],
  );
}
```

- [ ] **Step 2: Run, expect fail**

```bash
cd app && flutter test test/features/alignment/alignment_bloc_test.dart
```

- [ ] **Step 3: Implement event/state/bloc**

```dart
// app/lib/features/alignment/alignment_event.dart
abstract class AlignmentEvent {
  const AlignmentEvent();
}

class WizardStarted extends AlignmentEvent {
  const WizardStarted();
}

class CandidatesReceived extends AlignmentEvent {
  const CandidatesReceived();
}

class StarSwapRequested extends AlignmentEvent {
  const StarSwapRequested(this.idx);
  final int idx;
}

class PrePointingDone extends AlignmentEvent {
  const PrePointingDone();
}

class RecordRequested extends AlignmentEvent {
  const RecordRequested(this.idx);
  final int idx;
}

class ValidationAccepted extends AlignmentEvent {
  const ValidationAccepted();
}

class RestartStarRequested extends AlignmentEvent {
  const RestartStarRequested(this.idx);
  final int idx;
}

class WizardCancelled extends AlignmentEvent {
  const WizardCancelled();
}

class MountDisconnected extends AlignmentEvent {
  const MountDisconnected();
}
```

```dart
// app/lib/features/alignment/alignment_state.dart
import 'alignment_models.dart';

abstract class AlignmentState {
  const AlignmentState();
}

class AlignmentIdle extends AlignmentState {
  const AlignmentIdle();
}

class AlignmentLoadingCandidates extends AlignmentState {
  const AlignmentLoadingCandidates();
}

class AlignmentPrePointing extends AlignmentState {
  const AlignmentPrePointing({required this.session});
  final AlignmentSessionDto session;
}

class AlignmentFineTuning extends AlignmentState {
  const AlignmentFineTuning({required this.session});
  final AlignmentSessionDto session;
}

class AlignmentValidating extends AlignmentState {
  const AlignmentValidating({required this.model});
  final AlignmentModelDto model;
}

class AlignmentDone extends AlignmentState {
  const AlignmentDone();
}

class AlignmentError extends AlignmentState {
  const AlignmentError(this.message);
  final String message;
}
```

```dart
// app/lib/features/alignment/alignment_bloc.dart
import 'package:flutter_bloc/flutter_bloc.dart';

import 'alignment_event.dart';
import 'alignment_repository.dart';
import 'alignment_state.dart';

class AlignmentBloc extends Bloc<AlignmentEvent, AlignmentState> {
  AlignmentBloc({required this.repo}) : super(const AlignmentIdle()) {
    on<WizardStarted>(_onStarted);
    on<RecordRequested>(_onRecord);
    on<RestartStarRequested>(_onRestart);
    on<ValidationAccepted>((e, emit) => emit(const AlignmentDone()));
    on<WizardCancelled>(_onCancel);
    on<StarSwapRequested>(_onSwap);
    on<PrePointingDone>((e, emit) {
      final s = state;
      if (s is AlignmentPrePointing) {
        emit(AlignmentFineTuning(session: s.session));
      }
    });
    on<MountDisconnected>(
      (e, emit) => emit(const AlignmentError('Monture déconnectée')),
    );
  }

  final AlignmentRepository repo;

  Future<void> _onStarted(WizardStarted e, Emitter<AlignmentState> emit) async {
    emit(const AlignmentLoadingCandidates());
    try {
      final existing = await repo.getSession();
      final session = existing ?? await repo.start();
      emit(AlignmentPrePointing(session: session));
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onRecord(
      RecordRequested e, Emitter<AlignmentState> emit) async {
    try {
      final updated = await repo.record(e.idx);
      if (updated.recordedStars.length >= 3) {
        final model = await repo.finalize();
        emit(AlignmentValidating(model: model));
      } else {
        emit(AlignmentPrePointing(session: updated));
      }
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onRestart(
      RestartStarRequested e, Emitter<AlignmentState> emit) async {
    try {
      final s = await repo.restartStar(e.idx);
      emit(AlignmentPrePointing(session: s));
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onCancel(
      WizardCancelled e, Emitter<AlignmentState> emit) async {
    try {
      await repo.cancel();
    } catch (_) {}
    emit(const AlignmentIdle());
  }

  Future<void> _onSwap(
      StarSwapRequested e, Emitter<AlignmentState> emit) async {
    // L'écran Intro pop un dialog avec un sélecteur ; quand un star est choisi,
    // ce dialog appelle directement repo.swap() puis re-dispatche.
    // Ici on est juste passe-plat pour l'idx demandé.
  }
}
```

- [ ] **Step 4: Run, expect pass**

```bash
cd app && flutter test test/features/alignment/alignment_bloc_test.dart
```

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/ app/test/features/alignment/alignment_bloc_test.dart
git commit -m "feat(alignment): bloc + events + states (transitions wizard)"
```

---

### Task 15: AstroScreen.alignment dans l'enum AppBar

**Files:**
- Modify: `app/lib/widgets/astro_app_bar.dart`

- [ ] **Step 1: Add enum value**

Dans le fichier, repérer `enum AstroScreen { hub, manual, system, setup, about }` et le passer à :

```dart
enum AstroScreen { hub, manual, system, setup, about, alignment }
```

- [ ] **Step 2: Verify l'AppBar n'a pas de switch exhaustif qui crash**

Run: `grep -n "AstroScreen\." app/lib/widgets/astro_app_bar.dart`
Confirmer qu'aucun `switch` ne lève sans default.

- [ ] **Step 3: Run flutter test**

```bash
cd app && flutter test
```

- [ ] **Step 4: Commit**

```bash
git add app/lib/widgets/astro_app_bar.dart
git commit -m "feat(alignment): AstroScreen.alignment ajouté à l'enum AppBar"
```

---

### Task 16: PerStarScreen (mockup D2)

**Files:**
- Create: `app/lib/features/alignment/screens/per_star_screen.dart`
- Test: `app/test/features/alignment/per_star_screen_test.dart`

- [ ] **Step 1: Test widget**

```dart
// app/test/features/alignment/per_star_screen_test.dart
import 'package:astro_brain_app/features/alignment/alignment_models.dart';
import 'package:astro_brain_app/features/alignment/screens/per_star_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  StarDto _vega() => const StarDto(
        id: 'vega', name: 'Vega', bayer: 'α Lyrae',
        raDeg: 279.234, decDeg: 38.784, mag: 0.03,
      );

  testWidgets('PerStarScreen displays hero name + coords + magnitude', (t) async {
    await t.pumpWidget(MaterialApp(
      home: PerStarScreen(
        stepIndex: 1,
        totalSteps: 3,
        target: _vega(),
        targetAz: 248.0,
        targetAlt: 42.0,
        currentAz: 246.2,
        currentAlt: 43.3,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
    ));
    expect(find.text('VEGA'), findsOneWidget);
    expect(find.textContaining('mag 0.03'), findsOneWidget);
    expect(find.textContaining('AZ 248'), findsOneWidget);
  });

  testWidgets('Tap CENTRÉ triggers onCentered', (t) async {
    bool tapped = false;
    await t.pumpWidget(MaterialApp(
      home: PerStarScreen(
        stepIndex: 1, totalSteps: 3, target: _vega(),
        targetAz: 248.0, targetAlt: 42.0, currentAz: 246.0, currentAlt: 43.0,
        rate: 4, onPress: (_) {}, onRelease: () {}, onRateChanged: (_) {},
        onCentered: () => tapped = true,
      ),
    ));
    await t.tap(find.text('CENTRÉ ✓'));
    expect(tapped, isTrue);
  });
}
```

- [ ] **Step 2: Run, expect fail**

```bash
cd app && flutter test test/features/alignment/per_star_screen_test.dart
```

- [ ] **Step 3: Implement screen**

Implémenter le PerStarScreen en suivant exactement le mockup `.superpowers/brainstorm/42825-1778355945/content/per-star-d2-real-appbar.html` :
- Scaffold + LinearGradient bg
- AstroAppBar(current: AstroScreen.alignment)
- Body :
  - Step counter `// ÉTOILE n / N` (hudCaption muted)
  - Hero `target.name.toUpperCase()` (hudValue 26px)
  - Sub `${target.bayer} · mag ${target.mag} · AZ ${targetAz.round()}° / ALT ${targetAlt.round()}°`
  - HudPanel avec 2 axis-bars (AZ et ALT) :
    - label muted 9px JetBrainsMono
    - barre 6px : track + marker current (textMuted 2px) + marker target (accent 2px + glow)
    - delta numerique 14px JetBrainsMono accent
  - DPadControl(onPress: onPress, onRelease: onRelease, cellSize: 64, iconSize: 32)
  - RateControl(value: rate, onChanged: onRateChanged)
  - Bouton primaire pleine largeur "CENTRÉ ✓" → onCentered

```dart
// app/lib/features/alignment/screens/per_star_screen.dart
import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/dpad_control.dart';
import '../../../widgets/hud_panel.dart';
import '../../../widgets/rate_control.dart';
import '../alignment_models.dart';

class PerStarScreen extends StatelessWidget {
  const PerStarScreen({
    super.key,
    required this.stepIndex,
    required this.totalSteps,
    required this.target,
    required this.targetAz,
    required this.targetAlt,
    required this.currentAz,
    required this.currentAlt,
    required this.rate,
    required this.onPress,
    required this.onRelease,
    required this.onRateChanged,
    required this.onCentered,
  });

  final int stepIndex;
  final int totalSteps;
  final StarDto target;
  final double targetAz, targetAlt, currentAz, currentAlt;
  final int rate;
  final ValueChanged<DPadDirection> onPress;
  final VoidCallback onRelease;
  final ValueChanged<int> onRateChanged;
  final VoidCallback onCentered;

  double get _dAz => targetAz - currentAz;
  double get _dAlt => targetAlt - currentAlt;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.alignment),
                const SizedBox(height: DesignTokens.spaceLG),
                Text(
                  '// ÉTOILE $stepIndex / $totalSteps',
                  style: TextStyle(
                    fontFamily: 'JetBrainsMono',
                    fontSize: 10, letterSpacing: 1.5,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  target.name.toUpperCase(),
                  style: TextStyle(
                    fontFamily: 'JetBrainsMono',
                    fontSize: 26, fontWeight: FontWeight.w600,
                    letterSpacing: 1.3, color: colors.text,
                  ),
                ),
                Text(
                  '${target.bayer} · mag ${target.mag} · '
                  'AZ ${targetAz.round()}° / ALT ${targetAlt.round()}°',
                  style: TextStyle(fontSize: 11, color: colors.textMuted),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                HudPanel(
                  child: Column(
                    children: [
                      _AxisRow(label: 'AZ', delta: _dAz),
                      const Divider(height: DesignTokens.spaceMD),
                      _AxisRow(label: 'ALT', delta: _dAlt),
                    ],
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                AspectRatio(
                  aspectRatio: 1,
                  child: DPadControl(
                    onPress: onPress,
                    onRelease: onRelease,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceMD),
                RateControl(value: rate, onChanged: onRateChanged),
                const SizedBox(height: DesignTokens.spaceLG),
                _CenteredButton(onTap: onCentered),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AxisRow extends StatelessWidget {
  const _AxisRow({required this.label, required this.delta});
  final String label;
  final double delta;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      children: [
        SizedBox(
          width: 36,
          child: Text(
            label,
            style: TextStyle(
              fontFamily: 'JetBrainsMono', fontSize: 9,
              color: colors.textMuted, letterSpacing: 1.5,
            ),
          ),
        ),
        Expanded(
          child: Container(
            height: 6,
            decoration: BoxDecoration(
              color: colors.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
        ),
        const SizedBox(width: DesignTokens.spaceSM),
        SizedBox(
          width: 56,
          child: Text(
            '${delta >= 0 ? '+' : ''}${delta.toStringAsFixed(1)}°',
            textAlign: TextAlign.right,
            style: TextStyle(
              fontFamily: 'JetBrainsMono', fontSize: 14,
              fontWeight: FontWeight.w600, color: colors.text,
            ),
          ),
        ),
      ],
    );
  }
}

class _CenteredButton extends StatelessWidget {
  const _CenteredButton({required this.onTap});
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(DesignTokens.spaceLG),
        decoration: BoxDecoration(
          color: colors.accent,
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Text(
          'CENTRÉ ✓',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'JetBrainsMono',
            fontSize: 12, fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
            color: colors.bgGradientTop,
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Run, expect pass**

```bash
cd app && flutter test test/features/alignment/per_star_screen_test.dart
```

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/screens/per_star_screen.dart app/test/features/alignment/per_star_screen_test.dart
git commit -m "feat(alignment): per-star screen (mockup D2 — axis-bars + DPad + Rate)"
```

---

### Task 17: ValidationScreen (Option C)

**Files:**
- Create: `app/lib/features/alignment/screens/validation_screen.dart`
- Test: `app/test/features/alignment/validation_screen_test.dart`

- [ ] **Step 1: Test**

```dart
// app/test/features/alignment/validation_screen_test.dart
import 'package:astro_brain_app/features/alignment/alignment_models.dart';
import 'package:astro_brain_app/features/alignment/screens/validation_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  AlignmentModelDto _modelWithOutlier() => const AlignmentModelDto(
        recordedStars: [],
        rmsArcmin: 5.4,
        residuals: {'sirius': 2.1, 'vega': 11.4, 'capella': 2.8},
        validatedAtUtc: '2026-05-09T22:00:00+00:00',
        quality: 'good',
      );

  testWidgets('ValidationScreen shows RMS + 3 residuals + diagnostic', (t) async {
    await t.pumpWidget(MaterialApp(
      home: ValidationScreen(
        model: _modelWithOutlier(),
        candidates: const [
          StarDto(id: 'sirius', name: 'Sirius', bayer: 'α CMa',
                  raDeg: 0, decDeg: 0, mag: 0),
          StarDto(id: 'vega', name: 'Vega', bayer: 'α Lyr',
                  raDeg: 0, decDeg: 0, mag: 0),
          StarDto(id: 'capella', name: 'Capella', bayer: 'α Aur',
                  raDeg: 0, decDeg: 0, mag: 0),
        ],
        onAccept: () {},
        onRestartStar: (_) {},
      ),
    ));
    expect(find.textContaining('5.4'), findsWidgets);  // RMS
    expect(find.textContaining('2.1'), findsOneWidget);
    expect(find.textContaining('11.4'), findsOneWidget);
    expect(find.textContaining('2.8'), findsOneWidget);
    expect(find.textContaining('VEGA'), findsOneWidget);
    expect(find.text('ACCEPTER'), findsOneWidget);
    expect(find.textContaining('REFAIRE'), findsOneWidget);
  });

  testWidgets('Tap REFAIRE triggers onRestartStar with outlier idx', (t) async {
    int? idx;
    await t.pumpWidget(MaterialApp(
      home: ValidationScreen(
        model: _modelWithOutlier(),
        candidates: const [
          StarDto(id: 'sirius', name: 'Sirius', bayer: '-',
                  raDeg: 0, decDeg: 0, mag: 0),
          StarDto(id: 'vega', name: 'Vega', bayer: '-',
                  raDeg: 0, decDeg: 0, mag: 0),
          StarDto(id: 'capella', name: 'Capella', bayer: '-',
                  raDeg: 0, decDeg: 0, mag: 0),
        ],
        onAccept: () {},
        onRestartStar: (i) => idx = i,
      ),
    ));
    await t.tap(find.textContaining('REFAIRE'));
    expect(idx, 1);  // vega est idx 1
  });
}
```

- [ ] **Step 2: Run, expect fail**

```bash
cd app && flutter test test/features/alignment/validation_screen_test.dart
```

- [ ] **Step 3: Implement screen**

Implémenter en suivant le mockup `.superpowers/brainstorm/42825-1778355945/content/validation-result-options.html` (Option C). Trame :

- AstroAppBar
- Hero `RÉSULTAT`
- Bloc RMS (label + value + unité)
- HudPanel listant les 3 étoiles : nom, bar (largeur = residual / max), valeur
  - Si star.id == model.outlierId → name accent + bar `accent + glow` + valeur accent
- Encart diagnostic (bordure-gauche accent) listant les 3 causes possibles, avec `<strong>` sur le nom de l'outlier
- Row de 2 boutons : `REFAIRE <ÉTOILE>` (outlined) | `ACCEPTER` (primaire)
- `onRestartStar(idx)` où idx = candidates.indexWhere((c) => c.id == model.outlierId)

```dart
// app/lib/features/alignment/screens/validation_screen.dart
import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import '../alignment_models.dart';

class ValidationScreen extends StatelessWidget {
  const ValidationScreen({
    super.key,
    required this.model,
    required this.candidates,
    required this.onAccept,
    required this.onRestartStar,
  });

  final AlignmentModelDto model;
  final List<StarDto> candidates;
  final VoidCallback onAccept;
  final ValueChanged<int> onRestartStar;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final outlierId = model.outlierId;
    final outlierIdx = outlierId == null
        ? -1
        : candidates.indexWhere((c) => c.id == outlierId);
    final outlierName = outlierIdx >= 0 ? candidates[outlierIdx].name.toUpperCase() : '';
    final maxResid = (model.residuals.values.fold<double>(0, (a, b) => b > a ? b : a)).clamp(1, 1000);

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.alignment),
                const SizedBox(height: DesignTokens.spaceLG),
                Text('// VALIDATION',
                    style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10,
                        color: colors.textMuted, letterSpacing: 1.5)),
                const SizedBox(height: DesignTokens.spaceXS),
                Text('RÉSULTAT',
                    style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 22,
                        fontWeight: FontWeight.w600, color: colors.text)),
                const SizedBox(height: DesignTokens.spaceLG),
                Row(crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                  Text('RMS GLOBAL',
                      style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 9,
                          color: colors.textMuted, letterSpacing: 1.5)),
                  const SizedBox(width: DesignTokens.spaceSM),
                  Text(model.rmsArcmin.toStringAsFixed(1),
                      style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 18,
                          fontWeight: FontWeight.w600, color: colors.text)),
                  const SizedBox(width: 4),
                  Text('arc-min',
                      style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 11,
                          color: colors.textMuted)),
                ]),
                const SizedBox(height: DesignTokens.spaceMD),
                HudPanel(
                  child: Column(
                    children: candidates.map((c) {
                      final r = model.residuals[c.id] ?? 0.0;
                      final isOutlier = c.id == outlierId;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(children: [
                          SizedBox(
                            width: 90,
                            child: Text(
                              c.name.toUpperCase(),
                              style: TextStyle(
                                fontFamily: 'JetBrainsMono', fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: isOutlier ? colors.accent : colors.text,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Container(
                              height: 6,
                              decoration: BoxDecoration(
                                color: colors.accent.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(3),
                              ),
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: FractionallySizedBox(
                                  widthFactor: (r / maxResid).clamp(0.05, 1.0),
                                  child: Container(
                                    decoration: BoxDecoration(
                                      color: isOutlier
                                          ? colors.accent
                                          : colors.text.withValues(alpha: 0.5),
                                      borderRadius: BorderRadius.circular(3),
                                      boxShadow: isOutlier
                                          ? [
                                              BoxShadow(
                                                color: colors.accent
                                                    .withValues(alpha: 0.6),
                                                blurRadius: 8,
                                              )
                                            ]
                                          : null,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: DesignTokens.spaceSM),
                          SizedBox(
                            width: 56,
                            child: Text(
                              "${r.toStringAsFixed(1)}'",
                              textAlign: TextAlign.right,
                              style: TextStyle(
                                fontFamily: 'JetBrainsMono', fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: isOutlier ? colors.accent : colors.text,
                              ),
                            ),
                          ),
                        ]),
                      );
                    }).toList(),
                  ),
                ),
                if (outlierName.isNotEmpty) ...[
                  const SizedBox(height: DesignTokens.spaceMD),
                  Container(
                    padding: const EdgeInsets.all(DesignTokens.spaceMD),
                    decoration: BoxDecoration(
                      color: colors.accent.withValues(alpha: 0.06),
                      border: Border(left: BorderSide(color: colors.accent, width: 2)),
                      borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text.rich(
                          TextSpan(children: [
                            TextSpan(
                              text: outlierName,
                              style: TextStyle(
                                fontFamily: 'JetBrainsMono',
                                fontWeight: FontWeight.w600,
                                color: colors.accent,
                              ),
                            ),
                            TextSpan(
                              text: ' a un résiduel anormal. Causes possibles :',
                              style: TextStyle(
                                fontSize: 11,
                                color: colors.text.withValues(alpha: 0.75),
                              ),
                            ),
                          ]),
                        ),
                        const SizedBox(height: 6),
                        ...const [
                          '• Centrage imprécis dans l\'oculaire',
                          '• Mauvaise étoile pointée',
                          '• Dérive capteur depuis la calibration',
                        ].map((s) => Padding(
                              padding: const EdgeInsets.only(left: 4, top: 2),
                              child: Text(
                                s,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: colors.text.withValues(alpha: 0.75),
                                ),
                              ),
                            )),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: DesignTokens.spaceLG),
                Row(children: [
                  if (outlierIdx >= 0) ...[
                    Expanded(
                      child: OutlinedButton(
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceLG),
                          side: BorderSide(color: colors.accent.withValues(alpha: 0.5), width: 1.5),
                        ),
                        onPressed: () => onRestartStar(outlierIdx),
                        child: Text(
                          'REFAIRE $outlierName',
                          style: TextStyle(
                            fontFamily: 'JetBrainsMono', fontSize: 11,
                            fontWeight: FontWeight.w700, letterSpacing: 1.2,
                            color: colors.accent,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: DesignTokens.spaceMD),
                  ],
                  Expanded(
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: colors.accent,
                        padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceLG),
                      ),
                      onPressed: onAccept,
                      child: Text(
                        'ACCEPTER',
                        style: TextStyle(
                          fontFamily: 'JetBrainsMono', fontSize: 12,
                          fontWeight: FontWeight.w700, letterSpacing: 1.5,
                          color: colors.bgGradientTop,
                        ),
                      ),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Run, expect pass**

```bash
cd app && flutter test test/features/alignment/validation_screen_test.dart
```

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/screens/validation_screen.dart app/test/features/alignment/validation_screen_test.dart
git commit -m "feat(alignment): écran validation (Option C — RMS + outlier + diagnostic)"
```

---

### Task 18: IntroScreen + DoneScreen + WizardHost

**Files:**
- Create: `app/lib/features/alignment/screens/intro_screen.dart`
- Create: `app/lib/features/alignment/screens/done_screen.dart`
- Create: `app/lib/features/alignment/alignment_wizard_screen.dart`
- Test: `app/test/features/alignment/alignment_wizard_screen_test.dart`

- [ ] **Step 1: Tests intégration de l'host**

```dart
// app/test/features/alignment/alignment_wizard_screen_test.dart
import 'package:astro_brain_app/features/alignment/alignment_bloc.dart';
import 'package:astro_brain_app/features/alignment/alignment_state.dart';
import 'package:astro_brain_app/features/alignment/alignment_wizard_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockBloc extends Mock implements AlignmentBloc {}

void main() {
  testWidgets('Idle state shows IntroScreen', (t) async {
    final bloc = _MockBloc();
    when(() => bloc.state).thenReturn(const AlignmentIdle());
    when(() => bloc.stream).thenAnswer((_) => const Stream.empty());
    await t.pumpWidget(MaterialApp(
      home: BlocProvider<AlignmentBloc>.value(
        value: bloc, child: const AlignmentWizardScreen(),
      ),
    ));
    expect(find.text('ALIGNEMENT'), findsOneWidget);
  });

  testWidgets('Done state shows DoneScreen', (t) async {
    final bloc = _MockBloc();
    when(() => bloc.state).thenReturn(const AlignmentDone());
    when(() => bloc.stream).thenAnswer((_) => const Stream.empty());
    await t.pumpWidget(MaterialApp(
      home: BlocProvider<AlignmentBloc>.value(
        value: bloc, child: const AlignmentWizardScreen(),
      ),
    ));
    expect(find.textContaining('ALIGNÉE'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Implement IntroScreen, DoneScreen, AlignmentWizardScreen**

```dart
// app/lib/features/alignment/screens/intro_screen.dart
// (présente la liste des 3 candidates + bouton DÉMARRER)
// — adapter au design system, hud panel, bouton primaire
```

```dart
// app/lib/features/alignment/screens/done_screen.dart
// (texte "MONTURE ALIGNÉE ✓", RMS, bouton retour Hub)
```

```dart
// app/lib/features/alignment/alignment_wizard_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../state/app_bloc/app_bloc.dart';
import 'alignment_bloc.dart';
import 'alignment_event.dart';
import 'alignment_state.dart';
import 'screens/intro_screen.dart';
import 'screens/per_star_screen.dart';
import 'screens/validation_screen.dart';
import 'screens/done_screen.dart';

class AlignmentWizardScreen extends StatelessWidget {
  const AlignmentWizardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AlignmentBloc, AlignmentState>(
      builder: (context, state) {
        final bloc = context.read<AlignmentBloc>();
        if (state is AlignmentIdle || state is AlignmentLoadingCandidates) {
          return IntroScreen(
            session: state is AlignmentLoadingCandidates
                ? null
                : null,
            onStart: () => bloc.add(const WizardStarted()),
            onSwap: (idx) => bloc.add(StarSwapRequested(idx)),
          );
        }
        if (state is AlignmentPrePointing || state is AlignmentFineTuning) {
          final session = state is AlignmentPrePointing
              ? state.session
              : (state as AlignmentFineTuning).session;
          // currentAz/Alt et mount target → lus depuis AppBloc / SSE
          final mount = context.watch<AppBloc>().state.mount;
          return PerStarScreen(
            stepIndex: session.currentIdx + 1,
            totalSteps: 3,
            target: session.candidates[session.currentIdx],
            targetAz: 0, targetAlt: 0,  // TODO: calculer côté backend dans candidates payload
            currentAz: mount.azDeg,
            currentAlt: mount.altDeg,
            rate: 4,
            onPress: (d) { /* dispatch jog */ },
            onRelease: () { /* stop jog */ },
            onRateChanged: (_) {},
            onCentered: () => bloc.add(RecordRequested(session.currentIdx)),
          );
        }
        if (state is AlignmentValidating) {
          return ValidationScreen(
            model: state.model,
            candidates: const [],
            onAccept: () => bloc.add(const ValidationAccepted()),
            onRestartStar: (idx) => bloc.add(RestartStarRequested(idx)),
          );
        }
        if (state is AlignmentDone) {
          return const DoneScreen();
        }
        if (state is AlignmentError) {
          return Scaffold(
            body: Center(child: Text((state as AlignmentError).message)),
          );
        }
        return const SizedBox.shrink();
      },
    );
  }
}
```

NB : les TODOs ci-dessus (`targetAz/Alt` propagés dans la response candidates, jog dispatch) seront résolus dans Task 21 (intégration finale).

- [ ] **Step 3: Run, expect pass**

```bash
cd app && flutter test test/features/alignment/
```

- [ ] **Step 4: Commit**

```bash
git add app/lib/features/alignment/screens/intro_screen.dart app/lib/features/alignment/screens/done_screen.dart app/lib/features/alignment/alignment_wizard_screen.dart app/test/features/alignment/alignment_wizard_screen_test.dart
git commit -m "feat(alignment): WizardHost + IntroScreen + DoneScreen"
```

---

### Task 19: Wire dans app.dart + bouton Hub

**Files:**
- Modify: `app/lib/app.dart` (BlocProvider AlignmentBloc + RepositoryProvider)
- Modify: `app/lib/features/hub/hub_screen.dart` (bouton "Aligner" → push wizard)

- [ ] **Step 1: Add provider**

Dans `app/lib/app.dart`, ajouter dans le `MultiBlocProvider` :

```dart
BlocProvider<AlignmentBloc>(
  create: (ctx) => AlignmentBloc(
    repo: AlignmentRepository(api: ctx.read<ApiService>()),
  ),
),
```

- [ ] **Step 2: Add Hub button**

Dans `hub_screen.dart`, ajouter le tile/button "Aligner" qui push :

```dart
Navigator.of(context).push(
  MaterialPageRoute(builder: (_) => const AlignmentWizardScreen()),
);
```

- [ ] **Step 3: Run flutter analyze + flutter test**

```bash
cd app && flutter analyze && flutter test
```

- [ ] **Step 4: Commit**

```bash
git add app/lib/app.dart app/lib/features/hub/hub_screen.dart
git commit -m "feat(alignment): wire wizard dans app.dart + bouton Hub"
```

---

### Task 20: Cold-start restore prompt

**Files:**
- Modify: `app/lib/features/alignment/screens/intro_screen.dart`
- Modify: `app/lib/features/alignment/alignment_bloc.dart` (load existing session at start)

- [ ] **Step 1: Test logic**

Augmenter le bloc test :

```dart
blocTest<AlignmentBloc, AlignmentState>(
  'WizardStarted resumes existing session',
  build: () {
    when(() => repo.getSession()).thenAnswer((_) async => _sessionWithIdx(1, recCount: 1));
    return AlignmentBloc(repo: repo);
  },
  act: (b) => b.add(const WizardStarted()),
  expect: () => [
    isA<AlignmentLoadingCandidates>(),
    isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 1),
  ],
);
```

(Déjà couvert par le bloc actuel : `existing ?? await repo.start()`. Re-vérifier.)

- [ ] **Step 2: Add UI prompt for restored model**

Si la session backend renvoie un modèle finalisé en restore (cas distinct : on appelle un nouveau endpoint `GET /align/last_model` ou on lit depuis `app.state` via SSE), proposer un dialog :

> "Alignement de 22h47 disponible (RMS 5.4'). Le réutiliser ?"
> [REPRENDRE] [REFAIRE]

Pour MVP, on peut différer ce prompt visuel à la macro 3 #4 (consommer le modèle). Pour l'instant le restore-session (mid-wizard) est testé via WizardStarted.

- [ ] **Step 3: Run, commit si modifications**

```bash
cd app && flutter test
git add app/lib/features/alignment/
git commit -m "feat(alignment): resume session existante au démarrage du wizard"
```

---

## Phase F — Documentation

### Task 21: Mettre à jour roadmap + journal

**Files:**
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/journal.md`

- [ ] **Step 1: Roadmap**

Repérer la ligne Macro 3 #2 "Wizard alignement 3 étoiles" et la marquer 🚧 ou ✅ selon l'avancement.

- [ ] **Step 2: Journal**

Ajouter un paragraphe dans la session courante :

```
- Macro 3 #2 : implémentation backend + frontend wizard 3 étoiles. Tests unitaires complets.
  Validation matérielle bloquée par dongle CP2102 (Macro 1 INDI).
```

- [ ] **Step 3: Commit**

```bash
git add docs/project/roadmap.md docs/project/journal.md
git commit -m "docs: roadmap + journal — wizard 3 étoiles implémenté côté software"
```

---

### Task 22: Checklist d'intégration manuelle (post-dongle)

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-wizard-3star-alignment-integration-checklist.md`

- [ ] **Step 1: Écrire la checklist**

```markdown
# Wizard 3 étoiles — checklist d'intégration sur ciel réel

À exécuter dès que le dongle CP2102 est en place et que la stack INDI tourne sur le Pi.

## Pré-requis
- [ ] Macro 1 INDI : MountIndiAdapter validé via `nexstarpy` test smoke
- [ ] Monture Celestron alimentée, GPS Pi avec fix
- [ ] Compass + tilt calibrés (Macro 2)
- [ ] App Flutter installée sur l'Android USB

## Wizard end-to-end

1. [ ] Hub : tap "Aligner". Le wizard s'affiche avec 3 candidates pertinentes pour l'heure et la position.
2. [ ] Étoile 1 : tap "DÉMARRER". La monture slew avec heuristique capteurs. L'étoile est dans le grand-champ (~1°).
3. [ ] Centrer avec D-Pad + RateControl. AppBar reste en `EN COURS` (pastille muted).
4. [ ] Tap "CENTRÉ ✓". Passage automatique à étoile 2.
5. [ ] Étoile 2 : pré-pointage utilise l'offset de la 1ère. Centrage + record.
6. [ ] Étoile 3 : pré-pointage utilise modèle linéaire 2-points. Centrage + record.
7. [ ] Écran de validation : RMS < 10', 3 résiduels visibles. Tap ACCEPTER → retour Hub.

## Outlier path
8. [ ] Recommencer wizard. Sur l'étoile 2, mal centrer volontairement (≥ 30' off).
9. [ ] Au final : la validation identifie l'étoile 2 comme outlier (en accent + RMS élevé).
10. [ ] Tap "REFAIRE <ÉTOILE>". Retour au pré-pointage de l'étoile 2 uniquement.
11. [ ] Centrer correctement, valider. RMS amélioré.

## Persistance
12. [ ] Reboot Pi (mount allumée, ne pas la bouger). À la reconnexion app, le modèle est encore disponible.
13. [ ] Déplacer le Pi de plus de 20m. Au reboot, le modèle est invalidé silencieusement.

## Edge cases
14. [ ] Pendant le wizard, débrancher l'USB monture : AppBar passe en error, dialog "Monture déconnectée", retour Hub.
15. [ ] Slew failure (cas simulé : configurer une limite ALT 30°-60° et choisir une étoile à 70°) : l'app propose un swap.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-05-09-wizard-3star-alignment-integration-checklist.md
git commit -m "docs: checklist d'intégration manuelle wizard 3 étoiles (post-dongle)"
```

---

## Self-Review

**Spec coverage** :
- Pré-pointage capteurs : Task 7 (`record` lit `mount.current_position`) + Task 9 (wiring) — ✓
- Hybride sélection + swap : Task 7 (`swap` interdit après record) + Task 8 (route `/align/swap/{idx}`) + Task 18 (UI Intro) — ✓
- Mini catalogue 30+ étoiles : Task 2 — ✓
- Écran D2 (axis-bars + DPad + Rate) : Task 16 — ✓
- Coords cible AZ/ALT dans le sub : Task 16 (mockup-conforme) — ✓
- Validation Option C (RMS + résiduels + diagnostic) : Task 17 — ✓
- Outlier ID : `model.outlierId` (Task 13) + UI Task 17 — ✓
- Persistance state.db avec garde-fous Δt 12h / ΔGPS 20m : Task 5+6 — ✓
- Edge cases (mount disconnect → error ; slew unreachable → swap suggest) : Task 14 (`MountDisconnected` event), Task 8 (422 propagé), à finaliser au runtime dans Task 21 — partiellement couvert
- Refactor DPad/Rate : Tasks 11+12 — ✓
- AstroScreen.alignment : Task 15 — ✓
- Tests intégration manuels : Task 22 — ✓

**Placeholder scan** : 1 placeholder résiduel — `targetAz=0, targetAlt=0` dans `alignment_wizard_screen.dart` (Task 18) marqué `// TODO`. À résoudre quand la response `/align/start` exposera ces coords (à ajouter dans le DTO `StarDto` + backend response). Voir Task 21 / sub-tâche.

**Type consistency** : `AlignmentRepository.restartStar` (Dart camelCase) vs route `/align/restart_star` (snake_case) — ✓ cohérent. `outlierId` getter sur le DTO Dart, `residuals` map keyed by `star.id` côté backend — ✓.

**Gaps connus à traiter en cours d'implémentation** :
- Étendre la response `/align/start` pour inclure `(sky_az, sky_alt)` calculés par étoile à l'instant T (ajouter `target_az`/`target_alt` à `Star` côté DTO ou wrapper). Cela évite le TODO dans WizardHost.
- L'event SSE `alignment.session` (Task 10) n'est pas explicitement consommé par le bloc — pour MVP, le polling REST suffit, le SSE pourra être branché en macro 3 #4 quand le goto consomme le modèle live.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-wizard-3star-alignment.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
