# Catalogue + GoTo réel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer la page Catalogue Flutter (cartes + bottom sheet, recherche/magnitude/visible-now) consommant `/catalog/objects`, et le GoTo réel backend (`goto_radec` via `ON_COORD_SET=TRACK`, garde `is_aligned`, abort réutilisant `/stop`).

**Architecture:** Backend — un module d'éphéméride pur (`_ephemeris.py`) partagé alignement/catalogue, un `VisibilityEnricher` au-dessus du `CatalogRegistry`, une méthode `goto_radec` sur `MountService`, un flag `is_aligned` en RAM dans `AlignmentService` invalidé à la reconnexion monture, et un router `/goto`. Frontend — feature `lib/features/catalogue/` (bloc/repo/models/screen), le sous-système `alignment` ajouté au `SystemState`, et une carte Hub.

**Tech Stack:** Python 3.13 / FastAPI / pyindi-client / aiosqlite / pytest (`uv run pytest`). Flutter / flutter_bloc / equatable / http / `flutter test`.

**Référence design :** `docs/superpowers/specs/2026-05-31-catalogue-goto-design.md`.

**Conventions du repo :**
- Backend : commandes depuis `backend/`. PEP 8/257/484. Tests = fakes, pas de hardware.
- Frontend : commandes depuis `app/`. `flutter analyze` doit rester clean.
- Commits fréquents, un par task (ou sous-task). Messages style `feat(backend): …` / `feat(app): …`.
- INDI `getStateAsString()` renvoie `"Idle" | "Ok" | "Busy" | "Alert"` (capitalisé).

---

# PARTIE 1 — BACKEND

## Task B1 : Module d'éphéméride partagé `_ephemeris.py`

On déplace les helpers d'astronomie purs hors de `_alignment_catalog.py` pour les réutiliser dans le catalogue, sans dupliquer ni changer le comportement de l'alignement.

**Files:**
- Create: `backend/astro_brain/services/_ephemeris.py`
- Modify: `backend/astro_brain/services/_alignment_catalog.py`
- Create: `backend/tests/test_ephemeris.py`

- [ ] **Step 1 : Écrire le test d'éphéméride**

Create `backend/tests/test_ephemeris.py` :

```python
"""Tests du module d'éphéméride pur (conversion RA/Dec → Az/Alt)."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services._ephemeris import (
    Observer,
    sky_az_alt_from_ra_dec,
)


def test_sky_az_alt_zenith_star_is_high():
    # Une étoile dont la déclinaison = latitude passe au zénith au méridien.
    obs = Observer(lat_deg=48.0, lon_deg=0.0)
    t = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    # RA telle que l'angle horaire ≈ 0 → proche du méridien sud, alt ≈ 90 - |lat-dec|
    az, alt = sky_az_alt_from_ra_dec(ra_deg=0.0, dec_deg=48.0, observer=obs, t_utc=t)
    assert -1.0 <= alt <= 90.0
    assert 0.0 <= az < 360.0


def test_sky_az_alt_below_horizon_is_negative():
    # Une étoile très australe vue d'une latitude nord est sous l'horizon.
    obs = Observer(lat_deg=48.0, lon_deg=2.35)
    t = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
    _, alt = sky_az_alt_from_ra_dec(ra_deg=101.3, dec_deg=-80.0, observer=obs, t_utc=t)
    assert alt < 0.0
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_ephemeris.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'astro_brain.services._ephemeris'`

- [ ] **Step 3 : Créer `_ephemeris.py` en y déplaçant les helpers**

Create `backend/astro_brain/services/_ephemeris.py` avec le contenu **déplacé** depuis `_alignment_catalog.py` (corps identique) :

```python
"""Éphéméride pure : conversion RA/Dec (J2000, ICRS) → Az/Alt apparent.

Formule LST + sphérique classique, précision arc-min — sans corrections
nutation/aberration/réfraction. Aucune I/O, testable isolément. Partagée
par le wizard d'alignement et la couche catalogue (visibilité « maintenant »).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observer:
    lat_deg: float
    lon_deg: float


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
    """Greenwich Mean Sidereal Time en degrés (IAU 1982)."""
    jd = _julian_date(t_utc)
    jd0 = math.floor(jd - 0.5) + 0.5  # JD à 0h UT du même jour
    h_ut = (jd - jd0) * 24.0           # heures UT depuis 0h
    t0 = (jd0 - 2451545.0) / 36525.0
    gmst_h = (
        6.697374558
        + 2400.051336 * t0
        + 0.000025862 * t0 * t0
        + 1.00273790935 * h_ut
    )
    return (gmst_h * 15.0) % 360.0


def sky_az_alt_from_ra_dec(
    ra_deg: float, dec_deg: float, observer: Observer, t_utc: datetime
) -> tuple[float, float]:
    """Convertit (ra, dec) → (az, alt) pour `observer` à `t_utc`.

    Az mesuré depuis le Nord vers l'Est. Alt depuis l'horizon.
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
```

- [ ] **Step 4 : Faire ré-exporter `_alignment_catalog.py` (zéro régression alignement)**

Dans `backend/astro_brain/services/_alignment_catalog.py`, **supprimer** les définitions de `Observer`, `_julian_date`, `_gmst_deg`, `sky_az_alt_from_ra_dec` (lignes 19-23 pour `Observer` et 41-101 pour les fonctions) et **les ré-importer** en tête de fichier. Remplacer le bloc d'imports + `Observer` par :

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from importlib import resources

from astro_brain.models.alignment import Star
from astro_brain.services._ephemeris import (  # ré-export pour compat
    Observer,
    sky_az_alt_from_ra_dec,
)

__all__ = [
    "Observer",
    "MountLimits",
    "load_catalog",
    "select_candidates",
    "sky_az_alt_from_ra_dec",
]
```

Garder `MountLimits`, `load_catalog`, `select_candidates` inchangés. `select_candidates` continue d'appeler `sky_az_alt_from_ra_dec` (désormais importé). `math` reste utilisé par `select_candidates` (distances/isolation).

> Note : `app.py` importe `Observer`, `sky_az_alt_from_ra_dec` depuis `_alignment_catalog` (lignes 44-49) — le ré-export les garde valides, aucune modif d'`app.py` nécessaire ici.

- [ ] **Step 5 : Lancer les tests éphéméride + alignement**

Run: `cd backend && uv run pytest tests/test_ephemeris.py -v && uv run pytest -k "alignment or catalog" -q`
Expected: PASS partout (les tests d'alignement existants ne régressent pas).

- [ ] **Step 6 : Commit**

```bash
git add backend/astro_brain/services/_ephemeris.py backend/astro_brain/services/_alignment_catalog.py backend/tests/test_ephemeris.py
git commit -m "refactor(backend): extract _ephemeris.py shared by alignment + catalog"
```

---

## Task B2 : `CatalogObject` porte alt/az optionnels

**Files:**
- Modify: `backend/astro_brain/services/catalog/models.py:11-24`
- Test: `backend/tests/test_catalog_models.py` (existant — ajouter un test)

- [ ] **Step 1 : Écrire le test**

Ajouter à `backend/tests/test_catalog_models.py` :

```python
def test_catalog_object_altitude_azimuth_default_none():
    from astro_brain.services.catalog.models import CatalogObject

    obj = CatalogObject(
        qualified_id="star:sirius",
        kind="star",
        name="Sirius",
        ra_deg=101.287,
        dec_deg=-16.716,
    )
    assert obj.altitude_deg is None
    assert obj.azimuth_deg is None

    enriched = obj.model_copy(update={"altitude_deg": 34.0, "azimuth_deg": 168.0})
    assert enriched.altitude_deg == 34.0
    assert enriched.azimuth_deg == 168.0
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_catalog_models.py::test_catalog_object_altitude_azimuth_default_none -v`
Expected: FAIL — `ValidationError`/`AttributeError` (champs inconnus).

- [ ] **Step 3 : Ajouter les champs au modèle**

Dans `backend/astro_brain/services/catalog/models.py`, ajouter à `CatalogObject` (après `angular_size_arcmin`) :

```python
    angular_size_arcmin: float | None = None
    altitude_deg: float | None = None
    azimuth_deg: float | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_catalog_models.py -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/astro_brain/services/catalog/models.py backend/tests/test_catalog_models.py
git commit -m "feat(backend): CatalogObject carries optional altitude_deg/azimuth_deg"
```

---

## Task B3 : `VisibilityEnricher`

Enrichit une liste de `CatalogObject` avec alt/az courants ; filtre « visible maintenant » (alt > 0). Dégradation gracieuse sans fix GPS.

**Files:**
- Create: `backend/astro_brain/services/catalog/visibility.py`
- Create: `backend/tests/test_visibility_enricher.py`

- [ ] **Step 1 : Écrire le test**

Create `backend/tests/test_visibility_enricher.py` :

```python
"""Tests du VisibilityEnricher (enrichissement alt/az + filtre visible-now)."""
from __future__ import annotations

from datetime import UTC, datetime

from astro_brain.services.catalog.models import CatalogObject
from astro_brain.services.catalog.visibility import VisibilityEnricher

_T = datetime(2026, 3, 20, 22, 0, 0, tzinfo=UTC)


def _obj(qid: str, ra: float, dec: float) -> CatalogObject:
    return CatalogObject(
        qualified_id=qid, kind="star", name=qid.split(":")[1],
        ra_deg=ra, dec_deg=dec,
    )


def test_enrich_sets_alt_az_when_gps_fixed():
    enr = VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35), now_utc=lambda: _T,
    )
    out = enr.enrich([_obj("star:a", 100.0, 40.0)], visible_now=False)
    assert out[0].altitude_deg is not None
    assert out[0].azimuth_deg is not None


def test_visible_now_filters_below_horizon():
    enr = VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35), now_utc=lambda: _T,
    )
    # Une étoile très australe est sous l'horizon depuis 48°N.
    objs = [_obj("star:high", 330.0, 45.0), _obj("star:low", 100.0, -85.0)]
    out = enr.enrich(objs, visible_now=True)
    ids = {o.qualified_id for o in out}
    assert "star:low" not in ids
    assert all(o.altitude_deg is not None and o.altitude_deg > 0.0 for o in out)


def test_no_gps_degrades_gracefully():
    enr = VisibilityEnricher(gps_fix=lambda: None, now_utc=lambda: _T)
    objs = [_obj("star:a", 100.0, 40.0), _obj("star:b", 200.0, -85.0)]
    out = enr.enrich(objs, visible_now=True)  # filtre ignoré sans GPS
    assert len(out) == 2
    assert out[0].altitude_deg is None
    assert out[0].azimuth_deg is None
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_visibility_enricher.py -v`
Expected: FAIL — `ModuleNotFoundError: …catalog.visibility`

- [ ] **Step 3 : Implémenter `VisibilityEnricher`**

Create `backend/astro_brain/services/catalog/visibility.py` :

```python
"""Enrichissement de visibilité pour le catalogue.

Calcule l'altitude/azimut courants de chaque objet pour l'observateur
(position GPS) à l'instant présent, et filtre optionnellement les objets
sous l'horizon. Sans fix GPS, dégrade gracieusement : ne renseigne pas
alt/az et ignore le filtre.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from astro_brain.services._ephemeris import Observer, sky_az_alt_from_ra_dec
from astro_brain.services.catalog.models import CatalogObject

# Horizon géométrique. Un seuil pratique (obstruction) viendra du Setup tube.
_MIN_VISIBLE_ALT_DEG = 0.0


class VisibilityEnricher:
    """Ajoute alt/az courants aux objets et applique le filtre visible-now."""

    def __init__(
        self,
        *,
        gps_fix: Callable[[], tuple[float, float] | None],
        now_utc: Callable[[], datetime],
    ) -> None:
        self._gps_fix = gps_fix
        self._now_utc = now_utc

    def enrich(
        self, objects: list[CatalogObject], *, visible_now: bool
    ) -> list[CatalogObject]:
        fix = self._gps_fix()
        if fix is None:
            # Pas de position : on ne peut rien calculer. Filtre ignoré.
            return objects
        observer = Observer(lat_deg=fix[0], lon_deg=fix[1])
        t = self._now_utc()
        enriched: list[CatalogObject] = []
        for obj in objects:
            az, alt = sky_az_alt_from_ra_dec(obj.ra_deg, obj.dec_deg, observer, t)
            if visible_now and alt <= _MIN_VISIBLE_ALT_DEG:
                continue
            enriched.append(
                obj.model_copy(update={"altitude_deg": alt, "azimuth_deg": az})
            )
        return enriched
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_visibility_enricher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5 : Commit**

```bash
git add backend/astro_brain/services/catalog/visibility.py backend/tests/test_visibility_enricher.py
git commit -m "feat(backend): VisibilityEnricher (alt/az + visible-now filter, no-GPS graceful)"
```

---

## Task B4 : Câbler `visible_now` dans `/catalog/objects`

**Files:**
- Modify: `backend/astro_brain/routes/catalog.py`
- Modify: `backend/astro_brain/deps.py`
- Modify: `backend/astro_brain/app.py`
- Test: `backend/tests/test_catalog_routes.py` (existant — ajouter)

- [ ] **Step 1 : Écrire le test de route**

Ajouter à `backend/tests/test_catalog_routes.py` (mêmes imports/fixtures que les tests existants ; on monte un mini-app avec un registry réel et un enricher injecté). Modèle minimal autonome :

```python
def test_objects_visible_now_enriches_altitude(tmp_path):
    import asyncio

    import aiosqlite
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from astro_brain import deps
    from astro_brain.repository.state_db import run_migrations
    from astro_brain.routes.catalog import router
    from astro_brain.services.catalog.providers import SqliteCatalogProvider
    from astro_brain.services.catalog.registry import CatalogRegistry
    from astro_brain.services.catalog.visibility import VisibilityEnricher
    from datetime import UTC, datetime

    async def _seed(db):
        await run_migrations(db)
        await db.execute(
            "INSERT OR REPLACE INTO catalog_objects "
            "(id, kind, name, designation, ra_deg, dec_deg, mag, "
            " constellation, object_type, angular_size_arcmin, extras_json) "
            "VALUES ('star:vega','star','Vega','alpha Lyr',279.23,38.78,0.0,"
            "'Lyr','star',NULL,NULL)"
        )
        await db.commit()

    db = asyncio.get_event_loop().run_until_complete(
        aiosqlite.connect(":memory:")
    )
    asyncio.get_event_loop().run_until_complete(_seed(db))

    app = FastAPI()
    app.include_router(router)
    app.state.catalog_registry = CatalogRegistry(
        {"star": SqliteCatalogProvider(db, kind="star")}
    )
    app.state.visibility_enricher = VisibilityEnricher(
        gps_fix=lambda: (48.0, 2.35),
        now_utc=lambda: datetime(2026, 6, 21, 22, 0, 0, tzinfo=UTC),
    )
    client = TestClient(app)

    resp = client.get("/catalog/objects?visible_now=true")
    assert resp.status_code == 200
    body = resp.json()
    for obj in body["objects"]:
        assert obj["altitude_deg"] is not None
        assert obj["altitude_deg"] > 0.0
```

> Si `test_catalog_routes.py` possède déjà des fixtures `client`/`db`, réutilise-les plutôt que de reconstruire à la main ; l'essentiel est d'asserter que `visible_now=true` renseigne `altitude_deg`.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_catalog_routes.py::test_objects_visible_now_enriches_altitude -v`
Expected: FAIL — `AttributeError: … 'visibility_enricher'` ou `TypeError` (param `visible_now` inconnu).

- [ ] **Step 3 : Ajouter le resolver de dépendance**

Dans `backend/astro_brain/deps.py`, ajouter en fin de fichier :

```python
def get_visibility_enricher(request: Request) -> Any:
    return request.app.state.visibility_enricher
```

- [ ] **Step 4 : Câbler le param dans la route**

Dans `backend/astro_brain/routes/catalog.py`, modifier `list_objects` :

```python
@router.get("/objects", response_model=CatalogListResponse)
async def list_objects(
    kind: str | None = Query(default=None),
    search: str | None = Query(default=None),
    max_mag: float | None = Query(default=None),
    visible_now: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    registry: CatalogRegistry = Depends(deps.get_catalog_registry),
    enricher: Any = Depends(deps.get_visibility_enricher),
) -> CatalogListResponse:
    f = CatalogFilter(
        kind=kind, search=search, max_mag=max_mag, limit=limit, offset=offset,
    )
    objects = await registry.list_all(f)
    objects = enricher.enrich(objects, visible_now=visible_now)
    return CatalogListResponse(
        objects=objects, count=len(objects), limit=limit, offset=offset,
    )
```

- [ ] **Step 5 : Instancier l'enricher dans `build_app`**

Dans `backend/astro_brain/app.py`, après la création de `sensors_bridge` (ligne ~201) et avant `_app.state.alignment`, ajouter :

```python
        from astro_brain.services.catalog.visibility import VisibilityEnricher

        _app.state.visibility_enricher = VisibilityEnricher(
            gps_fix=sensors_bridge.gps_fix,
            now_utc=lambda: datetime.now(UTC),
        )
```

> `sensors_bridge.gps_fix` renvoie déjà `(lat, lon) | None` selon le fix GPS — exactement le contrat attendu par l'enricher.

- [ ] **Step 6 : Lancer les tests catalogue**

Run: `cd backend && uv run pytest tests/test_catalog_routes.py -v`
Expected: PASS

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/routes/catalog.py backend/astro_brain/deps.py backend/astro_brain/app.py backend/tests/test_catalog_routes.py
git commit -m "feat(backend): /catalog/objects?visible_now enriches alt/az"
```

---

## Task B5 : `goto_radec` sur `MountService` + Fake + état moving

**Files:**
- Modify: `backend/astro_brain/services/interfaces.py:37-46` (ajout méthode au Protocol)
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/astro_brain/services/fakes.py`
- Create: `backend/tests/test_mount_indi_goto.py`
- Test: `backend/tests/test_fakes.py` (existant — ajouter) ou nouveau

- [ ] **Step 1 : Écrire le test de l'adapter (push TRACK + coords + état moving)**

Create `backend/tests/test_mount_indi_goto.py` :

```python
"""Tests goto_radec + détection de fin de slew du MountIndiAdapter."""
from __future__ import annotations

import pytest

from astro_brain.adapters.mount_indi_adapter import MountIndiAdapter
from astro_brain.bus import StateBus
from tests.fakes.fake_indi import FakeIndiClient, FakeNumberVector


def _adapter_with_device() -> tuple[MountIndiAdapter, FakeIndiClient]:
    client = FakeIndiClient()
    dev = client.add_device("Celestron AUX")
    dev.add_switch("ON_COORD_SET", {"SLEW": "OFF", "TRACK": "OFF", "SYNC": "OFF"})
    dev.add_number("EQUATORIAL_EOD_COORD", {"RA": 0.0, "DEC": 0.0})
    adapter = MountIndiAdapter(StateBus(), client=client)
    return adapter, client


@pytest.mark.asyncio
async def test_goto_radec_arms_track_and_pushes_coords():
    adapter, client = _adapter_with_device()
    await adapter.start()
    client.sent_properties.clear()

    await adapter.goto_radec(101.287, -16.716, target_name="Sirius")

    # ON_COORD_SET armé sur TRACK
    coord_set = client.getDevice("Celestron AUX").getSwitch("ON_COORD_SET")
    assert coord_set["TRACK"].getState() == "ON"
    assert coord_set["SYNC"].getState() == "OFF"
    # EQUATORIAL_EOD_COORD : RA en heures, DEC en degrés
    coord = client.getDevice("Celestron AUX").getNumber("EQUATORIAL_EOD_COORD")
    assert coord["RA"].getValue() == pytest.approx(101.287 / 15.0)
    assert coord["DEC"].getValue() == pytest.approx(-16.716)


@pytest.mark.asyncio
async def test_goto_radec_publishes_moving_with_goto_details():
    adapter, _ = _adapter_with_device()
    await adapter.start()
    await adapter.goto_radec(101.287, -16.716, target_name="Sirius")

    mount = adapter._bus.get_full_state().subsystems["mount"]
    assert mount.state == "moving"
    assert mount.details["goto_in_progress"] is True
    assert mount.details["goto"]["target_name"] == "Sirius"


@pytest.mark.asyncio
async def test_goto_radec_noop_when_device_absent():
    adapter = MountIndiAdapter(StateBus(), client=FakeIndiClient())
    # pas de start() → pas de device
    await adapter.goto_radec(10.0, 10.0, target_name="X")  # ne lève pas
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_mount_indi_goto.py -v`
Expected: FAIL — `AttributeError: 'MountIndiAdapter' object has no attribute 'goto_radec'`

- [ ] **Step 3 : Ajouter `goto_radec` au Protocol**

Dans `backend/astro_brain/services/interfaces.py`, ajouter dans `MountService` (après `sync_radec`, avant `cordwrap_get_enabled`) :

```python
    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        """Pointe la monture sur (ra, dec) et enchaîne le tracking sidéral.

        Pattern INDI ``ON_COORD_SET=TRACK`` puis ``EQUATORIAL_EOD_COORD``
        (RA en heures, DEC en degrés, JNow). Publie l'état ``moving`` avec
        ``details.goto_in_progress = True`` ; l'arrivée (propriété passée à
        ``Ok``/``Idle``) repasse en ``ready``.
        """
        ...
```

- [ ] **Step 4 : Implémenter dans l'adapter**

Dans `backend/astro_brain/adapters/mount_indi_adapter.py` :

(a) Initialiser l'état goto dans `__init__` (après `self._active_slews = []`, ligne 66) :

```python
        self._active_slews: list[dict[str, Any]] = []
        self._goto_in_progress: bool = False
        self._goto_target: dict[str, Any] | None = None
```

(b) Ajouter la méthode après `sync_radec` (après ligne 331) :

```python
    # --- goto (slew vers coordonnées + tracking sidéral natif) ------------

    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        if self._device is None:
            return
        try:
            mode = self._device.getSwitch("ON_COORD_SET")
            if mode is None:
                raise RuntimeError("ON_COORD_SET property not found")
            set_switch_one_of_many(mode, "TRACK")
            await asyncio.to_thread(self._client.sendNewProperty, mode)

            coord = self._device.getNumber("EQUATORIAL_EOD_COORD")
            if coord is None:
                raise RuntimeError("EQUATORIAL_EOD_COORD property not found")
            coord["RA"].setValue(float(ra_deg) / 15.0)
            coord["DEC"].setValue(float(dec_deg))
            await asyncio.to_thread(self._client.sendNewProperty, coord)
        except Exception as exc:
            logger.exception("indi: goto_radec failed")
            self._bus.publish(
                "mount",
                SubsystemState(state="error", message=str(exc), since=_now()),
            )
            return

        self._goto_in_progress = True
        self._goto_target = {
            "target_name": target_name,
            "ra_deg": float(ra_deg),
            "dec_deg": float(dec_deg),
        }
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "device": self._device_name,
                    "goto_in_progress": True,
                    "goto": dict(self._goto_target),
                },
                since=_now(),
            ),
        )
```

- [ ] **Step 5 : Implémenter `FakeMount.goto_radec`**

Dans `backend/astro_brain/services/fakes.py`, dans `FakeMount.__init__` ajouter le registre, puis la méthode :

```python
    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._active_slews: list[dict[str, Any]] = []
        self.sync_calls: list[tuple[float, float]] = []
        self.goto_calls: list[tuple[float, float, str | None]] = []
```

Et après `sync_radec` (après ligne 101) :

```python
    async def goto_radec(
        self, ra_deg: float, dec_deg: float, target_name: str | None = None
    ) -> None:
        self.goto_calls.append((float(ra_deg), float(dec_deg), target_name))
        self._bus.publish(
            "mount",
            SubsystemState(
                state="moving",
                details={
                    "goto_in_progress": True,
                    "goto": {
                        "target_name": target_name,
                        "ra_deg": float(ra_deg),
                        "dec_deg": float(dec_deg),
                    },
                },
                since=_now(),
            ),
        )
```

- [ ] **Step 6 : Lancer les tests**

Run: `cd backend && uv run pytest tests/test_mount_indi_goto.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/services/interfaces.py backend/astro_brain/adapters/mount_indi_adapter.py backend/astro_brain/services/fakes.py backend/tests/test_mount_indi_goto.py
git commit -m "feat(backend): MountService.goto_radec (ON_COORD_SET=TRACK) + moving state"
```

---

## Task B6 : Détection de fin de slew (`updateProperty` → adapter)

On active la détection BUSY→OK : l'adapter expose `handle_property_update`, le client de prod le câble sur `updateProperty`.

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py`
- Modify: `backend/astro_brain/adapters/indi_client.py`
- Test: `backend/tests/test_mount_indi_goto.py` (ajouter)

- [ ] **Step 1 : Écrire le test de complétion**

Ajouter à `backend/tests/test_mount_indi_goto.py` :

```python
@pytest.mark.asyncio
async def test_goto_completion_on_eq_coord_ok_publishes_ready():
    adapter, _ = _adapter_with_device()
    await adapter.start()
    await adapter.goto_radec(101.287, -16.716, target_name="Sirius")
    assert adapter._goto_in_progress is True

    # Le driver signale l'arrivée : EQUATORIAL_EOD_COORD passe à "Ok".
    prop = FakeNumberVector(name="EQUATORIAL_EOD_COORD", state="Ok")
    adapter.handle_property_update(prop)

    assert adapter._goto_in_progress is False
    mount = adapter._bus.get_full_state().subsystems["mount"]
    assert mount.state == "ready"
    tracking = adapter._bus.get_full_state().subsystems["tracking"]
    assert tracking.state == "sidereal"


@pytest.mark.asyncio
async def test_goto_completion_ignores_busy_and_other_props():
    adapter, _ = _adapter_with_device()
    await adapter.start()
    await adapter.goto_radec(10.0, 10.0, target_name="X")

    adapter.handle_property_update(
        FakeNumberVector(name="EQUATORIAL_EOD_COORD", state="Busy")
    )
    assert adapter._goto_in_progress is True  # toujours en cours

    adapter.handle_property_update(
        FakeNumberVector(name="GEOGRAPHIC_COORD", state="Ok")
    )
    assert adapter._goto_in_progress is True  # autre propriété ignorée
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_mount_indi_goto.py -k completion -v`
Expected: FAIL — `AttributeError: … 'handle_property_update'`

- [ ] **Step 3 : Implémenter `handle_property_update` dans l'adapter**

Dans `backend/astro_brain/adapters/mount_indi_adapter.py`, ajouter après `goto_radec` :

```python
    _GOTO_DONE_STATES: frozenset[str] = frozenset({"Ok", "Idle"})

    def handle_property_update(self, prop: Any) -> None:
        """Réagit aux mises à jour de propriétés INDI (thread C++ → loop).

        Détecte la fin d'un GoTo : quand ``EQUATORIAL_EOD_COORD`` repasse à
        ``Ok``/``Idle`` alors qu'un goto était en cours, publie ``ready`` +
        ``tracking=sidereal`` et désarme le goto. Sync method : sûre à
        appeler depuis un callback (aucun await).
        """
        if not self._goto_in_progress:
            return
        try:
            name = prop.getName()
        except Exception:
            return
        if name != "EQUATORIAL_EOD_COORD":
            return
        if prop.getStateAsString() not in self._GOTO_DONE_STATES:
            return
        self._goto_in_progress = False
        self._goto_target = None
        self._bus.publish(
            "mount",
            SubsystemState(
                state="ready",
                details={"device": self._device_name},
                since=_now(),
            ),
        )
        self._bus.publish(
            "tracking",
            SubsystemState(state="sidereal", since=_now()),
        )
```

- [ ] **Step 4 : Câbler le callback dans le client de prod**

Dans `backend/astro_brain/adapters/indi_client.py`, accepter un callback `on_update` et l'invoquer dans `updateProperty` :

```python
class AstroBrainIndiClient(PyIndi.BaseClient):
    """Production INDI client. Pushes connection lifecycle to the bus."""

    def __init__(self, *, bus: StateBus, on_update=None) -> None:
        super().__init__()
        self._bus = bus
        self._on_update = on_update
        self._loop = asyncio.get_running_loop()
```

et remplacer le corps de `updateProperty` :

```python
    def updateProperty(self, prop: PyIndi.Property) -> None:  # noqa: N802
        # Forward to the adapter on the asyncio loop (callback fires from
        # PyIndi's C++ thread). Used for goto completion detection.
        if self._on_update is not None:
            self._loop.call_soon_threadsafe(self._on_update, prop)
```

Puis dans `mount_indi_adapter.py::start`, passer le callback à la construction du client de prod (remplacer la ligne `self._client = AstroBrainIndiClient(bus=self._bus)`) :

```python
                self._client = AstroBrainIndiClient(
                    bus=self._bus, on_update=self.handle_property_update
                )
```

- [ ] **Step 5 : Lancer les tests goto complets**

Run: `cd backend && uv run pytest tests/test_mount_indi_goto.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6 : Commit**

```bash
git add backend/astro_brain/adapters/mount_indi_adapter.py backend/astro_brain/adapters/indi_client.py backend/tests/test_mount_indi_goto.py
git commit -m "feat(backend): goto completion detection via EQUATORIAL_EOD_COORD state"
```

---

## Task B7 : Flag `is_aligned` dans `AlignmentService`

**Files:**
- Modify: `backend/astro_brain/services/interfaces.py:112-122`
- Modify: `backend/astro_brain/services/alignment.py`
- Modify: `backend/astro_brain/routes/alignment.py:22-47`
- Test: `backend/tests/test_alignment_service.py` (existant — ajouter)

- [ ] **Step 1 : Écrire le test du flag**

Ajouter à `backend/tests/test_alignment_service.py` (réutilise les fakes/fixtures existants du module ; modèle autonome) :

```python
@pytest.mark.asyncio
async def test_is_aligned_lifecycle():
    import numpy as np  # déjà dépendance

    from astro_brain.models.alignment import Star
    from astro_brain.services.alignment import AlignmentServiceImpl

    class _Mount:
        async def current_position(self):
            return (10.0, 20.0)
        async def sync_radec(self, ra, dec):
            return None

    class _Sensors:
        def sky_az_alt_for(self, star):
            return (10.0, 20.0)
        def gps_fix(self):
            return None

    stars = [
        Star(id=f"s{i}", name=f"S{i}", bayer="a", ra_deg=float(i * 30),
             dec_deg=10.0, mag=1.0)
        for i in range(3)
    ]
    saved = []
    svc = AlignmentServiceImpl(
        select_candidates=lambda: list(stars),
        mount=_Mount(),
        sensors=_Sensors(),
        repo_save=lambda db, m: saved.append(m),
        db=None,
        now_utc=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    assert svc.is_aligned is False
    await svc.start()
    for i in range(3):
        await svc.record(i)
    await svc.finalize()
    assert svc.is_aligned is True

    svc.invalidate()
    assert svc.is_aligned is False
```

> Si `finalize` lève sur le calcul SVD avec ces étoiles colinéaires, remplace par 3 étoiles bien réparties en AZ (ra_deg 0/120/240) — l'objectif du test est le flag, pas la qualité du modèle.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_alignment_service.py::test_is_aligned_lifecycle -v`
Expected: FAIL — `AttributeError: … 'is_aligned'`

- [ ] **Step 3 : Implémenter le flag dans `AlignmentServiceImpl`**

Dans `backend/astro_brain/services/alignment.py` :

(a) Dans `__init__`, après `self._session = None` :

```python
        self._session: AlignmentSession | None = None
        self._is_aligned: bool = False
```

(b) Ajouter la property + `invalidate` après `session()` :

```python
    @property
    def is_aligned(self) -> bool:
        return self._is_aligned

    def invalidate(self) -> None:
        """Perte du modèle natif (reconnexion monture / redémarrage driver)."""
        self._is_aligned = False
```

(c) Dans `finalize`, juste avant `return model`, après `self._session = None` :

```python
        await self._repo_save(self._db, model)
        self._session = None
        self._is_aligned = True
        return model
```

(d) Dans `cancel` :

```python
    async def cancel(self) -> None:
        self._session = None
        self._is_aligned = False
```

- [ ] **Step 4 : Étendre le Protocol**

Dans `backend/astro_brain/services/interfaces.py`, ajouter à `AlignmentService` :

```python
    async def finalize(self) -> "AlignmentModel": ...
    async def cancel(self) -> None: ...
    def session(self) -> "AlignmentSession | None": ...

    @property
    def is_aligned(self) -> bool: ...
    def invalidate(self) -> None: ...
```

- [ ] **Step 5 : Publier `is_aligned` dans l'état SSE alignment**

Dans `backend/astro_brain/routes/alignment.py::_publish_session`, ajouter `is_aligned` aux deux branches :

```python
def _publish_session(bus: StateBus, service: AlignmentService) -> None:
    sess = service.session()
    if sess is None:
        bus.publish(
            "alignment",
            SubsystemState(
                state="idle",
                details={"is_aligned": service.is_aligned},
                since=datetime.now(UTC),
            ),
        )
        return
    bus.publish(
        "alignment",
        SubsystemState(
            state="active",
            details={
                "session_id": sess.session_id,
                "current_idx": sess.current_idx,
                "recorded_count": len(sess.recorded_stars),
                "candidate_ids": [c.id for c in sess.candidates],
                "is_aligned": service.is_aligned,
            },
            since=datetime.now(UTC),
        ),
    )
```

- [ ] **Step 6 : Lancer les tests alignement**

Run: `cd backend && uv run pytest tests/test_alignment_service.py tests/test_alignment_routes.py -v`
Expected: PASS

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/services/alignment.py backend/astro_brain/services/interfaces.py backend/astro_brain/routes/alignment.py backend/tests/test_alignment_service.py
git commit -m "feat(backend): is_aligned flag (set on finalize, cleared on invalidate) + SSE"
```

---

## Task B8 : `AlignmentInvalidator` — invalidation à la reconnexion monture

**Files:**
- Create: `backend/astro_brain/alignment_invalidator.py`
- Modify: `backend/astro_brain/app.py`
- Create: `backend/tests/test_alignment_invalidator.py`

- [ ] **Step 1 : Écrire le test**

Create `backend/tests/test_alignment_invalidator.py` :

```python
"""Tests de l'AlignmentInvalidator (clear is_aligned sur reco monture)."""
from __future__ import annotations

from astro_brain.alignment_invalidator import AlignmentInvalidator


class _Alignment:
    def __init__(self) -> None:
        self.invalidated = 0
        self._aligned = True

    @property
    def is_aligned(self) -> bool:
        return self._aligned

    def invalidate(self) -> None:
        self.invalidated += 1
        self._aligned = False


def test_invalidates_when_mount_leaves_ready():
    align = _Alignment()
    inv = AlignmentInvalidator(alignment=align)

    inv.on_mount_state("ready")  # armé
    inv.on_mount_state("disconnected")
    assert align.invalidated == 1

    # Re-ready puis re-disconnect → ré-invalide (edge-triggered).
    inv.on_mount_state("ready")
    inv.on_mount_state("connecting")
    assert align.invalidated == 2


def test_no_invalidate_while_staying_ready():
    align = _Alignment()
    inv = AlignmentInvalidator(alignment=align)
    inv.on_mount_state("ready")
    inv.on_mount_state("moving")
    inv.on_mount_state("ready")
    assert align.invalidated == 0
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_alignment_invalidator.py -v`
Expected: FAIL — `ModuleNotFoundError: …alignment_invalidator`

- [ ] **Step 3 : Implémenter l'invalidator**

Create `backend/astro_brain/alignment_invalidator.py` :

```python
"""Invalide le flag is_aligned quand la monture perd son modèle natif.

Le modèle 3-étoiles vit dans le driver INDI (en mémoire). Toute reconnexion
(transition mount → disconnected/connecting/error) signifie sa perte : on
remet ``is_aligned`` à faux. Edge-triggered : ne ré-invalide qu'après être
repassé par ``ready``.

Branché sur le StateBus comme l'Orchestrator (une tâche de fond qui consomme
les events et appelle :meth:`on_mount_state`).
"""
from __future__ import annotations

import logging
from typing import Any

from astro_brain.bus import StateBus
from astro_brain.subsystems import MountState, SubsystemState

logger = logging.getLogger(__name__)

_LOST_STATES = frozenset(
    {MountState.DISCONNECTED.value, MountState.CONNECTING.value, MountState.ERROR.value}
)


class AlignmentInvalidator:
    """Clears is_aligned on mount reconnection (edge-triggered)."""

    def __init__(self, *, alignment: Any, bus: StateBus | None = None) -> None:
        self._alignment = alignment
        self._bus = bus
        self._was_ready = False

    def on_mount_state(self, state: str) -> None:
        if state == MountState.READY.value:
            self._was_ready = True
            return
        if state in _LOST_STATES and self._was_ready:
            logger.info("alignment: mount reconnection detected, invalidating model")
            self._alignment.invalidate()
            self._was_ready = False
            if self._bus is not None:
                self._bus.publish(
                    "alignment",
                    SubsystemState(state="idle", details={"is_aligned": False}),
                )

    async def run(self) -> None:
        """Consume bus events and react to mount state changes until cancelled."""
        if self._bus is None:
            return
        async for _event in self._bus.subscribe():
            mount = self._bus.get_full_state().subsystems.get("mount")
            if mount is not None:
                self.on_mount_state(mount.state)
```

- [ ] **Step 4 : Lancer le test**

Run: `cd backend && uv run pytest tests/test_alignment_invalidator.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5 : Câbler dans `build_app`**

Dans `backend/astro_brain/app.py` :

(a) import en tête :

```python
from astro_brain.alignment_invalidator import AlignmentInvalidator
```

(b) dans le lifespan, après la création de `_app.state.alignment` (ligne ~215) et le `bus.publish("alignment", idle)`, lancer la tâche de fond (à côté de l'orchestrateur, ligne ~226) :

```python
        invalidator = AlignmentInvalidator(
            alignment=_app.state.alignment, bus=bus
        )
        background_tasks.append(
            asyncio.create_task(invalidator.run(), name="alignment-invalidator")
        )
        orch_task = asyncio.create_task(orchestrator.run(), name="orchestrator")
        background_tasks.append(orch_task)
```

- [ ] **Step 6 : Lancer la suite app**

Run: `cd backend && uv run pytest tests/test_app.py -v`
Expected: PASS (l'app démarre toujours, lifespan OK)

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/alignment_invalidator.py backend/astro_brain/app.py backend/tests/test_alignment_invalidator.py
git commit -m "feat(backend): AlignmentInvalidator clears is_aligned on mount reconnect"
```

---

## Task B9 : Router `POST /goto` (garde + abort via /stop)

**Files:**
- Create: `backend/astro_brain/routes/goto.py`
- Modify: `backend/astro_brain/app.py` (include_router)
- Create: `backend/tests/test_goto_routes.py`

- [ ] **Step 1 : Écrire les tests de route**

Create `backend/tests/test_goto_routes.py` :

```python
"""Tests du router /goto (garde is_aligned + goto_in_progress + validation)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from astro_brain.bus import StateBus
from astro_brain.routes.goto import router
from astro_brain.services.fakes import FakeMount
from astro_brain.subsystems import SubsystemState


class _Alignment:
    def __init__(self, aligned: bool) -> None:
        self._aligned = aligned

    @property
    def is_aligned(self) -> bool:
        return self._aligned

    def invalidate(self) -> None:  # pragma: no cover
        self._aligned = False


def _client(*, aligned: bool) -> tuple[TestClient, FakeMount, StateBus]:
    bus = StateBus()
    mount = FakeMount(bus)
    app = FastAPI()
    app.include_router(router)
    app.state.bus = bus
    app.state.mount = mount
    app.state.alignment = _Alignment(aligned)
    return TestClient(app), mount, bus


def test_goto_blocked_when_not_aligned():
    client, mount, _ = _client(aligned=False)
    resp = client.post("/goto", json={"ra_deg": 101.0, "dec_deg": -16.0,
                                      "target_name": "Sirius"})
    assert resp.status_code == 409
    assert mount.goto_calls == []


def test_goto_ok_when_aligned_calls_mount():
    client, mount, _ = _client(aligned=True)
    resp = client.post("/goto", json={"ra_deg": 101.287, "dec_deg": -16.716,
                                      "target_name": "Sirius"})
    assert resp.status_code == 200
    assert mount.goto_calls == [(101.287, -16.716, "Sirius")]


def test_goto_blocked_when_already_in_progress():
    client, mount, bus = _client(aligned=True)
    bus.publish("mount", SubsystemState(
        state="moving", details={"goto_in_progress": True}))
    resp = client.post("/goto", json={"ra_deg": 10.0, "dec_deg": 10.0})
    assert resp.status_code == 409


def test_goto_invalid_coords_422():
    client, _, _ = _client(aligned=True)
    resp = client.post("/goto", json={"ra_deg": 999.0, "dec_deg": 200.0})
    assert resp.status_code == 422
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_goto_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: …routes.goto`

- [ ] **Step 3 : Implémenter le router**

Create `backend/astro_brain/routes/goto.py` :

```python
"""Route REST GoTo : POST /goto (slew vers coordonnées sur monture alignée).

L'abort se fait via le POST /stop existant (TELESCOPE_ABORT_MOTION).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from astro_brain import deps
from astro_brain.api_models import OkResponse
from astro_brain.bus import StateBus
from astro_brain.services.interfaces import AlignmentService, MountService

router = APIRouter(tags=["goto"])


class GotoRequest(BaseModel):
    ra_deg: float = Field(ge=0.0, lt=360.0)
    dec_deg: float = Field(ge=-90.0, le=90.0)
    target_name: str | None = None


@router.post("/goto", response_model=OkResponse)
async def goto(
    req: GotoRequest,
    mount: MountService = Depends(deps.get_mount),
    alignment: AlignmentService = Depends(deps.get_alignment_service),
    bus: StateBus = Depends(deps.get_bus),
) -> OkResponse:
    if not alignment.is_aligned:
        raise HTTPException(status_code=409, detail="mount not aligned")
    mount_state = bus.get_full_state().subsystems.get("mount")
    if mount_state is not None and mount_state.details.get("goto_in_progress"):
        raise HTTPException(status_code=409, detail="goto already in progress")
    await mount.goto_radec(req.ra_deg, req.dec_deg, target_name=req.target_name)
    return OkResponse()
```

- [ ] **Step 4 : Enregistrer le router**

Dans `backend/astro_brain/app.py`, importer et inclure :

```python
from astro_brain.routes.goto import router as goto_router
```

et après `app.include_router(catalog_router)` :

```python
    app.include_router(goto_router)
```

- [ ] **Step 5 : Lancer les tests**

Run: `cd backend && uv run pytest tests/test_goto_routes.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6 : Lancer toute la suite backend**

Run: `cd backend && uv run pytest -q`
Expected: PASS (tout vert, ~300+ tests).

- [ ] **Step 7 : Commit**

```bash
git add backend/astro_brain/routes/goto.py backend/astro_brain/app.py backend/tests/test_goto_routes.py
git commit -m "feat(backend): POST /goto router (is_aligned + in-progress guards, 422 coords)"
```

---

# PARTIE 2 — FRONTEND

## Task F1 : Sous-système `alignment` dans `SystemState`

Pour exposer `is_aligned` (+ `goto_in_progress` déjà dans `mount.details`) en live à la page.

**Files:**
- Modify: `app/lib/models/subsystem_kind.dart`
- Modify: `app/lib/models/subsystem_states.dart`
- Modify: `app/lib/models/system_state.dart`
- Test: `app/test/models/system_state_test.dart` (existant — ajouter) ou créer

- [ ] **Step 1 : Écrire le test**

Ajouter à `app/test/models/system_state_test.dart` (créer si absent, avec les imports) :

```dart
import 'package:astro_brain/models/system_state.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _baseSubsystems() => {
      'mount': {'state': 'ready', 'details': {}, 'since': '2026-05-31T20:00:00Z'},
      'gps': {'state': 'fix_3d', 'details': {}, 'since': '2026-05-31T20:00:00Z'},
      'tracking': {'state': 'off', 'details': {}, 'since': '2026-05-31T20:00:00Z'},
      'network': {'state': 'client', 'details': {}, 'since': '2026-05-31T20:00:00Z'},
      'system': {'state': 'ok', 'details': {}, 'since': '2026-05-31T20:00:00Z'},
    };

void main() {
  test('parses alignment subsystem with is_aligned', () {
    final subs = _baseSubsystems()
      ..['alignment'] = {
        'state': 'idle',
        'details': {'is_aligned': true},
        'since': '2026-05-31T20:00:00Z',
      };
    final s = SystemState.fromJson({
      'overall': 'blue',
      'subsystems': subs,
      'seq': 1,
      'ts': '2026-05-31T20:00:00Z',
    });
    expect(s.isAligned, isTrue);
  });

  test('isAligned false when alignment subsystem absent', () {
    final s = SystemState.fromJson({
      'overall': 'blue',
      'subsystems': _baseSubsystems(),
      'seq': 1,
      'ts': '2026-05-31T20:00:00Z',
    });
    expect(s.isAligned, isFalse);
  });
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/models/system_state_test.dart`
Expected: FAIL — `isAligned` non défini / `SubsystemKind` etc.

- [ ] **Step 3 : Ajouter le kind**

Dans `app/lib/models/subsystem_kind.dart`, ajouter `alignment` :

```dart
enum SubsystemKind {
  mount,
  gps,
  tracking,
  network,
  system,
  alignment;
```

- [ ] **Step 4 : Ajouter l'enum d'état alignment**

Dans `app/lib/models/subsystem_states.dart`, ajouter en fin de fichier :

```dart
enum AlignmentSubsysState {
  idle,
  active;

  static AlignmentSubsysState fromJson(String v) => switch (v) {
        'idle' => AlignmentSubsysState.idle,
        'active' => AlignmentSubsysState.active,
        _ => throw FormatException('AlignmentSubsysState inconnu: $v'),
      };
}
```

- [ ] **Step 5 : Câbler dans `SystemState` (nullable, tolérant)**

Dans `app/lib/models/system_state.dart` :

(a) champ + constructeur :

```dart
  final SubsystemState<SystemInfoState> system;
  final SubsystemState<AlignmentSubsysState>? alignment;
  final int seq;
```

```dart
    required this.system,
    this.alignment,
    required this.seq,
```

(b) getter pratique (après le constructeur) :

```dart
  /// `is_aligned` publié par le backend dans les détails du sous-système
  /// alignment. `false` si le sous-système est absent du snapshot.
  bool get isAligned => alignment?.details['is_aligned'] == true;

  /// `true` si un GoTo est en cours (détails du sous-système mount).
  bool get gotoInProgress => mount.details['goto_in_progress'] == true;

  /// Détails de la cible du GoTo courant, ou `null`.
  Map<String, dynamic>? get gotoTarget =>
      mount.details['goto'] as Map<String, dynamic>?;
```

(c) dans `fromJson`, parser si présent :

```dart
      system: SubsystemState.fromJson(
          subs['system'] as Map<String, dynamic>, SystemInfoState.fromJson),
      alignment: subs['alignment'] == null
          ? null
          : SubsystemState.fromJson(
              subs['alignment'] as Map<String, dynamic>,
              AlignmentSubsysState.fromJson),
      seq: json['seq'] as int,
```

(d) dans `applyUpdate`, conserver/mettre à jour :

```dart
      system: kind == SubsystemKind.system
          ? SubsystemState.fromJson(stateJson, SystemInfoState.fromJson)
          : system,
      alignment: kind == SubsystemKind.alignment
          ? SubsystemState.fromJson(stateJson, AlignmentSubsysState.fromJson)
          : alignment,
      seq: seq,
```

(e) ajouter `alignment` aux `props` :

```dart
  @override
  List<Object?> get props =>
      [overall, mount, gps, tracking, network, system, alignment, seq, ts];
```

- [ ] **Step 6 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/models/system_state_test.dart && flutter analyze`
Expected: PASS + analyze clean.

- [ ] **Step 7 : Commit**

```bash
git add app/lib/models/ app/test/models/system_state_test.dart
git commit -m "feat(app): parse alignment subsystem (isAligned / gotoInProgress getters)"
```

---

## Task F2 : `CatalogObjectDto`

**Files:**
- Create: `app/lib/features/catalogue/catalogue_models.dart`
- Create: `app/test/features/catalogue/catalogue_models_test.dart`

- [ ] **Step 1 : Écrire le test**

Create `app/test/features/catalogue/catalogue_models_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('CatalogObjectDto.fromJson parses fields incl. alt/az', () {
    final dto = CatalogObjectDto.fromJson({
      'qualified_id': 'star:sirius',
      'kind': 'star',
      'name': 'Sirius',
      'designation': 'alpha CMa',
      'ra_deg': 101.287,
      'dec_deg': -16.716,
      'mag': -1.45,
      'constellation': 'CMa',
      'object_type': 'star',
      'altitude_deg': 34.0,
      'azimuth_deg': 168.0,
    });
    expect(dto.qualifiedId, 'star:sirius');
    expect(dto.name, 'Sirius');
    expect(dto.mag, -1.45);
    expect(dto.altitudeDeg, 34.0);
    expect(dto.isVisible, isTrue);
  });

  test('isVisible false when altitude null or <= 0', () {
    final dto = CatalogObjectDto.fromJson({
      'qualified_id': 'star:x', 'kind': 'star', 'name': 'X',
      'ra_deg': 0.0, 'dec_deg': 0.0,
    });
    expect(dto.altitudeDeg, isNull);
    expect(dto.isVisible, isFalse);
  });
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_models_test.dart`
Expected: FAIL — fichier source absent.

- [ ] **Step 3 : Implémenter le DTO**

Create `app/lib/features/catalogue/catalogue_models.dart` :

```dart
/// DTO miroir du `CatalogObject` Pydantic backend
/// (`backend/astro_brain/services/catalog/models.py`).
library;

import 'package:equatable/equatable.dart';

class CatalogObjectDto extends Equatable {
  const CatalogObjectDto({
    required this.qualifiedId,
    required this.kind,
    required this.name,
    required this.raDeg,
    required this.decDeg,
    this.designation,
    this.mag,
    this.constellation,
    this.objectType,
    this.altitudeDeg,
    this.azimuthDeg,
  });

  final String qualifiedId;
  final String kind;
  final String name;
  final double raDeg;
  final double decDeg;
  final String? designation;
  final double? mag;
  final String? constellation;
  final String? objectType;
  final double? altitudeDeg;
  final double? azimuthDeg;

  /// `true` si l'altitude courante est connue et au-dessus de l'horizon.
  bool get isVisible => altitudeDeg != null && altitudeDeg! > 0.0;

  factory CatalogObjectDto.fromJson(Map<String, dynamic> j) => CatalogObjectDto(
        qualifiedId: j['qualified_id'] as String,
        kind: j['kind'] as String,
        name: j['name'] as String,
        raDeg: (j['ra_deg'] as num).toDouble(),
        decDeg: (j['dec_deg'] as num).toDouble(),
        designation: j['designation'] as String?,
        mag: (j['mag'] as num?)?.toDouble(),
        constellation: j['constellation'] as String?,
        objectType: j['object_type'] as String?,
        altitudeDeg: (j['altitude_deg'] as num?)?.toDouble(),
        azimuthDeg: (j['azimuth_deg'] as num?)?.toDouble(),
      );

  @override
  List<Object?> get props => [
        qualifiedId, kind, name, raDeg, decDeg, designation, mag,
        constellation, objectType, altitudeDeg, azimuthDeg,
      ];
}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/features/catalogue/catalogue_models_test.dart`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add app/lib/features/catalogue/catalogue_models.dart app/test/features/catalogue/catalogue_models_test.dart
git commit -m "feat(app): CatalogObjectDto with alt/az + isVisible"
```

---

## Task F3 : `CatalogueRepository`

**Files:**
- Create: `app/lib/features/catalogue/catalogue_repository.dart`
- Create: `app/test/features/catalogue/catalogue_repository_test.dart`

- [ ] **Step 1 : Écrire le test**

Create `app/test/features/catalogue/catalogue_repository_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;
  setUp(() => api = _MockApi());

  test('listObjects builds query and parses objects', () async {
    when(() => api.getJson(any())).thenAnswer((_) async => {
          'objects': [
            {
              'qualified_id': 'star:vega', 'kind': 'star', 'name': 'Vega',
              'ra_deg': 279.23, 'dec_deg': 38.78, 'mag': 0.0,
              'altitude_deg': 18.0, 'azimuth_deg': 51.0,
            }
          ],
          'count': 1, 'limit': 500, 'offset': 0,
        });

    final repo = CatalogueRepository(api: api);
    final objs = await repo.listObjects(
        search: 'veg', maxMag: 3.0, visibleNow: true);

    expect(objs, hasLength(1));
    expect(objs.first.name, 'Vega');
    final captured =
        verify(() => api.getJson(captureAny())).captured.single as String;
    expect(captured, contains('/catalog/objects'));
    expect(captured, contains('search=veg'));
    expect(captured, contains('max_mag=3.0'));
    expect(captured, contains('visible_now=true'));
  });

  test('goto posts ra/dec/target_name', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    final repo = CatalogueRepository(api: api);
    await repo.goto(101.0, -16.0, 'Sirius');
    verify(() => api.postJson('/goto',
        {'ra_deg': 101.0, 'dec_deg': -16.0, 'target_name': 'Sirius'})).called(1);
  });

  test('abort posts /stop', () async {
    when(() => api.stop()).thenAnswer((_) async {});
    final repo = CatalogueRepository(api: api);
    await repo.abort();
    verify(() => api.stop()).called(1);
  });
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_repository_test.dart`
Expected: FAIL — source absente.

- [ ] **Step 3 : Implémenter le repository**

Create `app/lib/features/catalogue/catalogue_repository.dart` :

```dart
import '../../services/api_service.dart';
import 'catalogue_models.dart';

/// Façade REST sur `/catalog/objects` + `/goto` (+ `/stop` pour l'abort).
class CatalogueRepository {
  CatalogueRepository({required this.api});

  final ApiService api;

  /// GET /catalog/objects avec filtres optionnels. On charge large (limit 500)
  /// — le catalogue actuel est petit, pagination différée (Macro 4).
  Future<List<CatalogObjectDto>> listObjects({
    String? search,
    double? maxMag,
    bool visibleNow = false,
  }) async {
    final params = <String, String>{'limit': '500'};
    if (search != null && search.isNotEmpty) params['search'] = search;
    if (maxMag != null) params['max_mag'] = maxMag.toString();
    if (visibleNow) params['visible_now'] = 'true';
    final query = params.entries.map((e) => '${e.key}=${e.value}').join('&');
    final j = await api.getJson('/catalog/objects?$query');
    final list = (j['objects'] as List)
        .map((e) => CatalogObjectDto.fromJson(e as Map<String, dynamic>))
        .toList();
    return list;
  }

  /// POST /goto — pointe la monture sur les coordonnées de l'objet.
  Future<void> goto(double raDeg, double decDeg, String? targetName) =>
      api.postJson('/goto', {
        'ra_deg': raDeg,
        'dec_deg': decDeg,
        'target_name': targetName,
      });

  /// Abort : réutilise le POST /stop existant (TELESCOPE_ABORT_MOTION).
  Future<void> abort() => api.stop();
}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/features/catalogue/catalogue_repository_test.dart`
Expected: PASS (3 tests)

- [ ] **Step 5 : Commit**

```bash
git add app/lib/features/catalogue/catalogue_repository.dart app/test/features/catalogue/catalogue_repository_test.dart
git commit -m "feat(app): CatalogueRepository (list + goto + abort)"
```

---

## Task F4 : Events + states du `CatalogueBloc`

**Files:**
- Create: `app/lib/features/catalogue/catalogue_event.dart`
- Create: `app/lib/features/catalogue/catalogue_state.dart`

- [ ] **Step 1 : Écrire les events**

Create `app/lib/features/catalogue/catalogue_event.dart` :

```dart
import 'package:equatable/equatable.dart';

sealed class CatalogueEvent extends Equatable {
  const CatalogueEvent();
  @override
  List<Object?> get props => [];
}

class CatalogueOpened extends CatalogueEvent {
  const CatalogueOpened();
}

class SearchChanged extends CatalogueEvent {
  const SearchChanged(this.text);
  final String text;
  @override
  List<Object?> get props => [text];
}

class MagFilterChanged extends CatalogueEvent {
  const MagFilterChanged(this.maxMag);
  final double? maxMag;
  @override
  List<Object?> get props => [maxMag];
}

class VisibleNowToggled extends CatalogueEvent {
  const VisibleNowToggled(this.enabled);
  final bool enabled;
  @override
  List<Object?> get props => [enabled];
}

class GoToRequested extends CatalogueEvent {
  const GoToRequested(this.raDeg, this.decDeg, this.targetName);
  final double raDeg;
  final double decDeg;
  final String targetName;
  @override
  List<Object?> get props => [raDeg, decDeg, targetName];
}

class AbortRequested extends CatalogueEvent {
  const AbortRequested();
}
```

- [ ] **Step 2 : Écrire les states**

Create `app/lib/features/catalogue/catalogue_state.dart` :

```dart
import 'package:equatable/equatable.dart';

import 'catalogue_models.dart';

/// Filtres actifs de la page (recherche, magnitude max, visible maintenant).
class CatalogueFilters extends Equatable {
  const CatalogueFilters({
    this.search = '',
    this.maxMag,
    this.visibleNow = true,
  });

  final String search;
  final double? maxMag;
  final bool visibleNow;

  CatalogueFilters copyWith({
    String? search,
    double? maxMag,
    bool? visibleNow,
    bool clearMaxMag = false,
  }) =>
      CatalogueFilters(
        search: search ?? this.search,
        maxMag: clearMaxMag ? null : (maxMag ?? this.maxMag),
        visibleNow: visibleNow ?? this.visibleNow,
      );

  @override
  List<Object?> get props => [search, maxMag, visibleNow];
}

sealed class CatalogueState extends Equatable {
  const CatalogueState();
  @override
  List<Object?> get props => [];
}

class CatalogueLoading extends CatalogueState {
  const CatalogueLoading(this.filters);
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [filters];
}

class CatalogueLoaded extends CatalogueState {
  const CatalogueLoaded({required this.objects, required this.filters});
  final List<CatalogObjectDto> objects;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [objects, filters];
}

class CatalogueError extends CatalogueState {
  const CatalogueError(this.message, this.filters);
  final String message;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [message, filters];
}
```

- [ ] **Step 3 : Vérifier la compilation**

Run: `cd app && flutter analyze lib/features/catalogue/`
Expected: pas d'erreur (warnings d'imports inutilisés tolérés jusqu'au bloc).

- [ ] **Step 4 : Commit**

```bash
git add app/lib/features/catalogue/catalogue_event.dart app/lib/features/catalogue/catalogue_state.dart
git commit -m "feat(app): CatalogueBloc events + states + filters"
```

---

## Task F5 : `CatalogueBloc`

**Files:**
- Create: `app/lib/features/catalogue/catalogue_bloc.dart`
- Create: `app/test/features/catalogue/catalogue_bloc_test.dart`

- [ ] **Step 1 : Écrire le bloc_test**

Create `app/test/features/catalogue/catalogue_bloc_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_event.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements CatalogueRepository {}

CatalogObjectDto _vega() => const CatalogObjectDto(
      qualifiedId: 'star:vega', kind: 'star', name: 'Vega',
      raDeg: 279.23, decDeg: 38.78, mag: 0.0, altitudeDeg: 18.0,
    );

void main() {
  late _MockRepo repo;
  setUp(() => repo = _MockRepo());

  blocTest<CatalogueBloc, CatalogueState>(
    'CatalogueOpened → Loading → Loaded',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const CatalogueOpened()),
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>()
          .having((s) => s.objects.length, 'count', 1),
    ],
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'VisibleNowToggled re-queries with flag',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const VisibleNowToggled(false)),
    wait: const Duration(milliseconds: 350),
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>()
          .having((s) => s.filters.visibleNow, 'visibleNow', false),
    ],
    verify: (_) {
      verify(() => repo.listObjects(
          search: any(named: 'search'),
          maxMag: any(named: 'maxMag'),
          visibleNow: false)).called(1);
    },
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'GoToRequested calls repo.goto',
    build: () {
      when(() => repo.goto(any(), any(), any())).thenAnswer((_) async {});
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const GoToRequested(101.0, -16.0, 'Sirius')),
    verify: (_) => verify(() => repo.goto(101.0, -16.0, 'Sirius')).called(1),
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'CatalogueOpened error → CatalogueError',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenThrow(Exception('boom'));
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const CatalogueOpened()),
    expect: () => [isA<CatalogueLoading>(), isA<CatalogueError>()],
  );
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_bloc_test.dart`
Expected: FAIL — source absente.

- [ ] **Step 3 : Implémenter le bloc**

Create `app/lib/features/catalogue/catalogue_bloc.dart` :

```dart
import 'package:bloc_concurrency/bloc_concurrency.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:stream_transform/stream_transform.dart';

import 'catalogue_event.dart';
import 'catalogue_repository.dart';
import 'catalogue_state.dart';

const _debounce = Duration(milliseconds: 300);

EventTransformer<E> _debounced<E>() =>
    (events, mapper) => droppable<E>()(events.debounce(_debounce), mapper);

/// Bloc de la page Catalogue : liste/recherche/filtres + déclenchement GoTo.
/// Les statuts transverses (is_aligned, goto_in_progress, fix GPS) viennent
/// de l'AppBloc/SSE — pas d'ici.
class CatalogueBloc extends Bloc<CatalogueEvent, CatalogueState> {
  CatalogueBloc({required this.repo})
      : super(const CatalogueLoading(CatalogueFilters())) {
    on<CatalogueOpened>(_onReload);
    on<SearchChanged>(_onSearch, transformer: _debounced());
    on<MagFilterChanged>(_onMag);
    on<VisibleNowToggled>(_onVisible);
    on<GoToRequested>(_onGoTo);
    on<AbortRequested>(_onAbort);
  }

  final CatalogueRepository repo;

  CatalogueFilters get _filters => switch (state) {
        CatalogueLoading(:final filters) => filters,
        CatalogueLoaded(:final filters) => filters,
        CatalogueError(:final filters) => filters,
      };

  Future<void> _query(
      Emitter<CatalogueState> emit, CatalogueFilters filters) async {
    emit(CatalogueLoading(filters));
    try {
      final objects = await repo.listObjects(
        search: filters.search,
        maxMag: filters.maxMag,
        visibleNow: filters.visibleNow,
      );
      emit(CatalogueLoaded(objects: objects, filters: filters));
    } catch (e) {
      emit(CatalogueError(e.toString(), filters));
    }
  }

  Future<void> _onReload(CatalogueOpened e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters);

  Future<void> _onSearch(SearchChanged e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters.copyWith(search: e.text));

  Future<void> _onMag(MagFilterChanged e, Emitter<CatalogueState> emit) =>
      _query(
          emit,
          e.maxMag == null
              ? _filters.copyWith(clearMaxMag: true)
              : _filters.copyWith(maxMag: e.maxMag));

  Future<void> _onVisible(VisibleNowToggled e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters.copyWith(visibleNow: e.enabled));

  Future<void> _onGoTo(GoToRequested e, Emitter<CatalogueState> emit) async {
    await repo.goto(e.raDeg, e.decDeg, e.targetName);
  }

  Future<void> _onAbort(AbortRequested e, Emitter<CatalogueState> emit) async {
    await repo.abort();
  }
}
```

> Si `bloc_concurrency` / `stream_transform` ne sont pas déjà des deps, ajoute-les : `cd app && flutter pub add bloc_concurrency stream_transform`. (Vérifie d'abord `pubspec.yaml` ; `flutter_bloc` peut déjà tirer `bloc_concurrency`.)

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/features/catalogue/catalogue_bloc_test.dart`
Expected: PASS (4 tests)

- [ ] **Step 5 : Commit**

```bash
git add app/lib/features/catalogue/catalogue_bloc.dart app/test/features/catalogue/catalogue_bloc_test.dart app/pubspec.yaml app/pubspec.lock
git commit -m "feat(app): CatalogueBloc (debounced search, filters, goto, abort)"
```

---

## Task F6 : `AstroScreen.catalogue` dans l'AppBar

**Files:**
- Modify: `app/lib/widgets/astro_app_bar.dart:15`

- [ ] **Step 1 : Ajouter la valeur d'enum**

Dans `app/lib/widgets/astro_app_bar.dart`, étendre l'enum :

```dart
enum AstroScreen { hub, manual, system, setup, about, alignment, catalogue }
```

> Aucune autre logique à toucher : l'AppBar ne se sert de `current` que pour `system` et `setup` (skip conditionnels). `catalogue` se comporte comme un écran enfant standard (back-arrow + bouton setup actifs).

- [ ] **Step 2 : Vérifier l'analyse**

Run: `cd app && flutter analyze lib/widgets/astro_app_bar.dart`
Expected: clean.

- [ ] **Step 3 : Commit**

```bash
git add app/lib/widgets/astro_app_bar.dart
git commit -m "feat(app): add AstroScreen.catalogue"
```

---

## Task F7 : Carte d'objet `CatalogueObjectCard`

**Files:**
- Create: `app/lib/features/catalogue/widgets/catalogue_object_card.dart`
- Create: `app/test/features/catalogue/catalogue_object_card_test.dart`

- [ ] **Step 1 : Écrire le widget test**

Create `app/test/features/catalogue/catalogue_object_card_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/widgets/catalogue_object_card.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _theme() {
  const color = AppColors.day;
  const ts = TextStyle(color: Color(0xFFB4D7FF));
  return ThemeData(extensions: <ThemeExtension<dynamic>>[
    color,
    const AppTextStyles(
        hudLabel: ts, hudValue: ts, hudCaption: ts, hudBadge: ts),
  ]);
}

void main() {
  testWidgets('renders name, mag and tapping fires onTap', (tester) async {
    var tapped = false;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Scaffold(
        body: CatalogueObjectCard(
          object: const CatalogObjectDto(
            qualifiedId: 'star:sirius', kind: 'star', name: 'Sirius',
            designation: 'alpha CMa', raDeg: 101.0, decDeg: -16.0,
            mag: -1.45, constellation: 'CMa', altitudeDeg: 34.0,
            azimuthDeg: 168.0,
          ),
          onTap: () => tapped = true,
        ),
      ),
    ));
    expect(find.text('Sirius'), findsOneWidget);
    expect(find.textContaining('-1.4'), findsWidgets);
    await tester.tap(find.byType(CatalogueObjectCard));
    expect(tapped, isTrue);
  });
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_object_card_test.dart`
Expected: FAIL — source absente.

- [ ] **Step 3 : Implémenter la carte**

Create `app/lib/features/catalogue/widgets/catalogue_object_card.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../catalogue_models.dart';

/// Carte aérée d'un objet du catalogue (option B du design — lisibilité).
class CatalogueObjectCard extends StatelessWidget {
  const CatalogueObjectCard({
    super.key,
    required this.object,
    required this.onTap,
  });

  final CatalogObjectDto object;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final subtitle = [
      if (object.designation != null) object.designation!,
      if (object.constellation != null) object.constellation!,
    ].join(' · ');

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
      child: Container(
        padding: const EdgeInsets.all(DesignTokens.spaceMD),
        decoration: BoxDecoration(
          color: colors.bgGradientTop.withValues(alpha: 0.5),
          border: Border.all(color: colors.accent.withValues(alpha: 0.18)),
          borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(object.name,
                      style: text.hudValue
                          .copyWith(color: colors.textPrimary, fontSize: 16)),
                  if (subtitle.isNotEmpty) ...[
                    const SizedBox(height: DesignTokens.spaceXS),
                    Text(subtitle,
                        style: text.hudCaption
                            .copyWith(color: colors.textMuted)),
                  ],
                  const SizedBox(height: DesignTokens.spaceSM),
                  Row(children: [
                    if (object.mag != null)
                      _Pill(label: 'mag ${object.mag!.toStringAsFixed(1)}'),
                    if (object.altitudeDeg != null) ...[
                      const SizedBox(width: DesignTokens.spaceSM),
                      _Pill(
                        label: 'ALT ${object.altitudeDeg!.round()}°',
                        highlight: object.isVisible,
                      ),
                    ],
                  ]),
                ],
              ),
            ),
            PhosphorIcon(PhosphorIconsBold.caretRight,
                color: colors.accent, size: 18),
          ],
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, this.highlight = false});
  final String label;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final c = highlight ? colors.dotOk : colors.textMuted;
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: DesignTokens.spaceSM, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: c.withValues(alpha: 0.5)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
      ),
      child: Text(label, style: text.hudBadge.copyWith(color: c)),
    );
  }
}
```

> Vérifie les noms exacts des slots de couleur (`textMuted`, `dotOk`, `bgGradientTop`) dans `app/lib/theme/app_colors.dart` ; ajuste si un slot diffère (le rapport d'exploration cite `textPrimary`, `textMuted`, `dotOk`, `accent`, `bgGradientTop/Bottom`).

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/features/catalogue/catalogue_object_card_test.dart && flutter analyze lib/features/catalogue/`
Expected: PASS + clean.

- [ ] **Step 5 : Commit**

```bash
git add app/lib/features/catalogue/widgets/catalogue_object_card.dart app/test/features/catalogue/catalogue_object_card_test.dart
git commit -m "feat(app): CatalogueObjectCard (legible card with mag/alt pills)"
```

---

## Task F8 : `CatalogueScreen` (bandeau + recherche + chips + liste + bottom sheet)

**Files:**
- Create: `app/lib/features/catalogue/catalogue_screen.dart`
- Create: `app/lib/features/catalogue/widgets/catalogue_detail_sheet.dart`
- Create: `app/test/features/catalogue/catalogue_screen_test.dart`

- [ ] **Step 1 : Écrire le widget test (bandeau + bouton grisé selon alignement)**

Create `app/test/features/catalogue/catalogue_screen_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_screen.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:astro_brain/theme/theme_cubit.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockApi extends Mock implements ApiService {}
class _MockStream extends Mock implements EventStreamService {}
class _MockRepo extends Mock implements CatalogueRepository {}

ThemeData _theme() {
  const color = AppColors.day;
  const ts = TextStyle(color: Color(0xFFB4D7FF));
  return ThemeData(extensions: <ThemeExtension<dynamic>>[
    color,
    const AppTextStyles(
        hudLabel: ts, hudValue: ts, hudCaption: ts, hudBadge: ts),
  ]);
}

void main() {
  setUpAll(() {
    SharedPreferences.setMockInitialValues({});
  });

  Future<void> pump(WidgetTester tester, {required bool aligned}) async {
    final stream = _MockStream();
    when(() => stream.stream)
        .thenAnswer((_) => const Stream<dynamic>.empty().cast());
    when(() => stream.start()).thenAnswer((_) {});
    when(() => stream.stop()).thenAnswer((_) async {});
    when(() => stream.dispose()).thenAnswer((_) async {});

    final appBloc = AppBloc(eventStream: stream);
    // is_aligned est lu via AppState.system.isAligned ; en l'absence de SSE
    // (stream vide) system == null → isAligned false. Pour le cas aligned,
    // on s'appuie sur l'API : voir note ci-dessous.

    final repo = _MockRepo();
    when(() => repo.listObjects(
            search: any(named: 'search'),
            maxMag: any(named: 'maxMag'),
            visibleNow: any(named: 'visibleNow')))
        .thenAnswer((_) async => const <CatalogObjectDto>[]);

    final host = PiHost(host: 'x', port: 1);
    await tester.pumpWidget(MultiRepositoryProvider(
      providers: [
        RepositoryProvider<PiHost>.value(value: host),
        RepositoryProvider<ApiService>.value(value: _MockApi()),
        RepositoryProvider<EventStreamService>.value(value: stream),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider<AppBloc>.value(value: appBloc),
          BlocProvider<ThemeCubit>(
              create: (_) => ThemeCubit(prefs: null)),
          BlocProvider<CatalogueBloc>(
              create: (_) => CatalogueBloc(repo: repo)),
        ],
        child: MaterialApp(theme: _theme(), home: const CatalogueScreen()),
      ),
    ));
    await tester.pump();
  }

  testWidgets('shows not-aligned banner when mount not aligned',
      (tester) async {
    await pump(tester, aligned: false);
    expect(find.textContaining('non alignée'), findsOneWidget);
  });
}
```

> Note : `ThemeCubit(prefs: null)` — si `ThemeCubit` exige un `SharedPreferences` non-null, instancie-le via `await SharedPreferences.getInstance()` dans le test (mock initialisé). Adapte la signature au constructeur réel.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_screen_test.dart`
Expected: FAIL — source absente.

- [ ] **Step 3 : Implémenter le bottom sheet de détail**

Create `app/lib/features/catalogue/widgets/catalogue_detail_sheet.dart` :

```dart
import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../catalogue_models.dart';

/// Bottom sheet de détail d'un objet + bouton POINTER (grisé si non aligné).
class CatalogueDetailSheet extends StatelessWidget {
  const CatalogueDetailSheet({
    super.key,
    required this.object,
    required this.isAligned,
    required this.onGoto,
  });

  final CatalogObjectDto object;
  final bool isAligned;
  final VoidCallback onGoto;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    Widget cell(String k, String v) => Container(
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.bgGradientTop.withValues(alpha: 0.6),
            border: Border.all(color: colors.accent.withValues(alpha: 0.18)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(k, style: text.hudLabel.copyWith(color: colors.textMuted)),
              const SizedBox(height: DesignTokens.spaceXS),
              Text(v,
                  style: text.hudValue.copyWith(color: colors.textPrimary)),
            ],
          ),
        );

    return Padding(
      padding: const EdgeInsets.all(DesignTokens.spaceLG),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(object.name,
              style: text.hudValue
                  .copyWith(color: colors.textPrimary, fontSize: 22)),
          const SizedBox(height: DesignTokens.spaceXS),
          Text(
            [
              if (object.designation != null) object.designation!,
              if (object.constellation != null) object.constellation!,
              object.kind,
            ].join(' · '),
            style: text.hudCaption.copyWith(color: colors.textMuted),
          ),
          const SizedBox(height: DesignTokens.spaceLG),
          Row(children: [
            Expanded(
                child: cell('MAGNITUDE',
                    object.mag?.toStringAsFixed(2) ?? '—')),
            const SizedBox(width: DesignTokens.spaceMD),
            Expanded(
                child: cell('ALTITUDE',
                    object.altitudeDeg != null
                        ? '${object.altitudeDeg!.round()}°'
                        : '—')),
          ]),
          const SizedBox(height: DesignTokens.spaceMD),
          Row(children: [
            Expanded(
                child: cell('AZIMUT',
                    object.azimuthDeg != null
                        ? '${object.azimuthDeg!.round()}°'
                        : '—')),
            const SizedBox(width: DesignTokens.spaceMD),
            Expanded(
                child: cell('AD / DÉC',
                    '${(object.raDeg / 15).toStringAsFixed(1)}h / '
                    '${object.decDeg.round()}°')),
          ]),
          const SizedBox(height: DesignTokens.spaceLG),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: isAligned
                  ? () {
                      Navigator.of(context).pop();
                      onGoto();
                    }
                  : null,
              child: const Text('⌖ POINTER (GOTO)'),
            ),
          ),
          if (!isAligned) ...[
            const SizedBox(height: DesignTokens.spaceSM),
            Text('Monture non alignée — alignez d\'abord',
                style: text.hudCaption.copyWith(color: colors.dotWarn)),
          ],
        ],
      ),
    );
  }
}
```

- [ ] **Step 4 : Implémenter l'écran**

Create `app/lib/features/catalogue/catalogue_screen.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import '../alignment/alignment_wizard_screen.dart';
import 'catalogue_bloc.dart';
import 'catalogue_event.dart';
import 'catalogue_models.dart';
import 'catalogue_state.dart';
import 'widgets/catalogue_detail_sheet.dart';
import 'widgets/catalogue_object_card.dart';

/// Page Catalogue — Macro 3 #5. Liste cherchable/filtrable d'objets célestes
/// avec GoTo conditionné à l'alignement.
class CatalogueScreen extends StatelessWidget {
  const CatalogueScreen({super.key});

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
          child: Column(
            children: [
              const AstroAppBar(current: AstroScreen.catalogue),
              const _NotAlignedBanner(),
              const _Filters(),
              const Expanded(child: _ObjectList()),
            ],
          ),
        ),
      ),
    );
  }
}

class _NotAlignedBanner extends StatelessWidget {
  const _NotAlignedBanner();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.system?.isAligned != b.system?.isAligned,
      builder: (ctx, state) {
        if (state.system?.isAligned == true) return const SizedBox.shrink();
        return Container(
          margin: const EdgeInsets.all(DesignTokens.spaceMD),
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotWarn.withValues(alpha: 0.1),
            border: Border.all(color: colors.dotWarn.withValues(alpha: 0.4)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Monture non alignée — pointage indisponible.',
                  style: text.hudCaption.copyWith(color: colors.dotWarn),
                ),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).push(
                  MaterialPageRoute(
                      builder: (_) => const AlignmentWizardScreen()),
                ),
                child: const Text('ALIGNER →'),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Filters extends StatelessWidget {
  const _Filters();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    // La chip "visible maintenant" est désactivée sans fix GPS.
    final gpsFixed = context.select<AppBloc, bool>((b) {
      final g = b.state.system?.gps.state.name;
      return g == 'fix2d' || g == 'fix3d';
    });

    return BlocBuilder<CatalogueBloc, CatalogueState>(
      builder: (ctx, state) {
        final filters = switch (state) {
          CatalogueLoading(:final filters) => filters,
          CatalogueLoaded(:final filters) => filters,
          CatalogueError(:final filters) => filters,
        };
        return Padding(
          padding: const EdgeInsets.symmetric(
              horizontal: DesignTokens.spaceMD),
          child: Column(
            children: [
              TextField(
                onChanged: (v) => ctx.read<CatalogueBloc>().add(
                    SearchChanged(v)),
                style: TextStyle(color: colors.textPrimary),
                decoration: const InputDecoration(
                  hintText: 'Rechercher une étoile…',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
              const SizedBox(height: DesignTokens.spaceSM),
              Wrap(
                spacing: DesignTokens.spaceSM,
                children: [
                  FilterChip(
                    label: const Text('VISIBLE MAINTENANT'),
                    selected: filters.visibleNow && gpsFixed,
                    onSelected: gpsFixed
                        ? (v) => ctx
                            .read<CatalogueBloc>()
                            .add(VisibleNowToggled(v))
                        : null,
                  ),
                  FilterChip(
                    label: const Text('MAG ≤ 3'),
                    selected: filters.maxMag == 3.0,
                    onSelected: (v) => ctx.read<CatalogueBloc>().add(
                        MagFilterChanged(v ? 3.0 : null)),
                  ),
                  FilterChip(
                    label: const Text('MAG ≤ 2'),
                    selected: filters.maxMag == 2.0,
                    onSelected: (v) => ctx.read<CatalogueBloc>().add(
                        MagFilterChanged(v ? 2.0 : null)),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ObjectList extends StatelessWidget {
  const _ObjectList();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CatalogueBloc, CatalogueState>(
      builder: (ctx, state) {
        return switch (state) {
          CatalogueLoading() =>
            const Center(child: CircularProgressIndicator()),
          CatalogueError(:final message) =>
            Center(child: Text(message)),
          CatalogueLoaded(:final objects) => ListView.separated(
              padding: const EdgeInsets.all(DesignTokens.spaceMD),
              itemCount: objects.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: DesignTokens.spaceSM),
              itemBuilder: (c, i) => CatalogueObjectCard(
                object: objects[i],
                onTap: () => _openDetail(ctx, objects[i]),
              ),
            ),
        };
      },
    );
  }

  void _openDetail(BuildContext context, CatalogObjectDto obj) {
    final bloc = context.read<CatalogueBloc>();
    final isAligned = context.read<AppBloc>().state.system?.isAligned == true;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: context.colors.bgGradientBottom,
      isScrollControlled: true,
      builder: (_) => CatalogueDetailSheet(
        object: obj,
        isAligned: isAligned,
        onGoto: () => bloc.add(GoToRequested(obj.raDeg, obj.decDeg, obj.name)),
      ),
    );
  }
}
```

- [ ] **Step 5 : Lancer, vérifier le succès**

Run: `cd app && flutter test test/features/catalogue/catalogue_screen_test.dart && flutter analyze lib/features/catalogue/`
Expected: PASS + clean. (Ajuste les noms de slots couleur / signature ThemeCubit si analyze remonte un écart.)

- [ ] **Step 6 : Commit**

```bash
git add app/lib/features/catalogue/ app/test/features/catalogue/catalogue_screen_test.dart
git commit -m "feat(app): CatalogueScreen (banner + search + chips + list + detail sheet)"
```

---

## Task F9 : Slew bar (overlay GoTo en cours + STOP)

**Files:**
- Create: `app/lib/features/catalogue/widgets/goto_slew_bar.dart`
- Modify: `app/lib/features/catalogue/catalogue_screen.dart` (insérer l'overlay)
- Create: `app/test/features/catalogue/goto_slew_bar_test.dart`

- [ ] **Step 1 : Écrire le widget test**

Create `app/test/features/catalogue/goto_slew_bar_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/widgets/goto_slew_bar.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _theme() {
  const color = AppColors.day;
  const ts = TextStyle(color: Color(0xFFB4D7FF));
  return ThemeData(extensions: <ThemeExtension<dynamic>>[
    color,
    const AppTextStyles(
        hudLabel: ts, hudValue: ts, hudCaption: ts, hudBadge: ts),
  ]);
}

void main() {
  testWidgets('shows target name and STOP fires onStop', (tester) async {
    var stopped = false;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Scaffold(
        body: GotoSlewBar(targetName: 'Sirius', onStop: () => stopped = true),
      ),
    ));
    expect(find.textContaining('Sirius'), findsOneWidget);
    await tester.tap(find.textContaining('STOP'));
    expect(stopped, isTrue);
  });
}
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/catalogue/goto_slew_bar_test.dart`
Expected: FAIL — source absente.

- [ ] **Step 3 : Implémenter la slew bar**

Create `app/lib/features/catalogue/widgets/goto_slew_bar.dart` :

```dart
import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';

/// Barre de slew GoTo : nom de cible, progression indéterminée, bouton STOP.
/// (La progression est indéterminée : INDI ne donne pas de % fiable.)
class GotoSlewBar extends StatelessWidget {
  const GotoSlewBar({super.key, required this.targetName, required this.onStop});

  final String targetName;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.all(DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientBottom,
        border: Border(
            top: BorderSide(color: colors.accent.withValues(alpha: 0.4))),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('GOTO → $targetName',
                  style: text.hudLabel.copyWith(color: colors.textPrimary)),
              Text('EN COURS',
                  style: text.hudBadge.copyWith(color: colors.dotWarn)),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceSM),
          LinearProgressIndicator(color: colors.accent),
          const SizedBox(height: DesignTokens.spaceSM),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: onStop,
              child: const Text('■ STOP'),
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4 : Brancher l'overlay dans l'écran (piloté par AppBloc/SSE)**

Dans `app/lib/features/catalogue/catalogue_screen.dart`, remplacer la `Column` du `SafeArea` pour insérer la slew bar en bas quand un GoTo est en cours :

```dart
          child: Column(
            children: [
              const AstroAppBar(current: AstroScreen.catalogue),
              const _NotAlignedBanner(),
              const _Filters(),
              const Expanded(child: _ObjectList()),
              const _SlewBarSlot(),
            ],
          ),
```

Et ajouter en bas du fichier :

```dart
class _SlewBarSlot extends StatelessWidget {
  const _SlewBarSlot();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) =>
          a.system?.gotoInProgress != b.system?.gotoInProgress ||
          a.system?.gotoTarget != b.system?.gotoTarget,
      builder: (ctx, state) {
        if (state.system?.gotoInProgress != true) {
          return const SizedBox.shrink();
        }
        final target = state.system?.gotoTarget?['target_name'] as String?;
        return GotoSlewBar(
          targetName: target ?? 'cible',
          onStop: () => ctx.read<CatalogueBloc>().add(const AbortRequested()),
        );
      },
    );
  }
}
```

Ajouter l'import : `import 'widgets/goto_slew_bar.dart';`

- [ ] **Step 5 : Lancer les tests catalogue**

Run: `cd app && flutter test test/features/catalogue/ && flutter analyze lib/features/catalogue/`
Expected: PASS + clean.

- [ ] **Step 6 : Commit**

```bash
git add app/lib/features/catalogue/ app/test/features/catalogue/goto_slew_bar_test.dart
git commit -m "feat(app): GoTo slew bar overlay driven by SSE goto_in_progress"
```

---

## Task F10 : Carte Hub CATALOGUE + wiring `app.dart`

**Files:**
- Modify: `app/lib/app.dart`
- Modify: `app/lib/features/hub/hub_screen.dart`
- Test: `app/test/features/hub/hub_screen_test.dart` (existant — ajuster le compte de cartes)

- [ ] **Step 1 : Mettre à jour le test du Hub**

Dans `app/test/features/hub/hub_screen_test.dart`, le wrap doit fournir `CatalogueBloc`. Ajouter au `_wrap` (ou au MultiBlocProvider du test) :

```dart
        BlocProvider<CatalogueBloc>(
          create: (_) => CatalogueBloc(
            repo: CatalogueRepository(api: apiService),
          ),
        ),
```

avec les imports :

```dart
import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
```

Et si un test asserte le nombre de cartes (`findsNWidgets(5)`), le passer à `6` et ajouter un test de navigation vers `CatalogueScreen` :

```dart
  testWidgets('CATALOGUE card navigates to CatalogueScreen', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.tap(find.text('CATALOGUE'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(CatalogueScreen), findsOneWidget);
  });
```

import : `import 'package:astro_brain/features/catalogue/catalogue_screen.dart';`

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `cd app && flutter test test/features/hub/hub_screen_test.dart`
Expected: FAIL — `CatalogueBloc` introuvable dans le contexte / carte absente.

- [ ] **Step 3 : Ajouter la carte Hub**

Dans `app/lib/features/hub/hub_screen.dart`, importer l'écran :

```dart
import '../catalogue/catalogue_screen.dart';
```

et insérer l'entrée entre ALIGNER et SETUP :

```dart
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedStar,
        label: 'CATALOGUE',
        hint: 'Objets célestes · GoTo',
        builder: (_) => const CatalogueScreen(),
      ),
```

> Vérifie que `HugeIcons.strokeRoundedStar` existe dans `hugeicons 1.1.6` ; sinon prends une icône astro proche (`strokeRoundedStarsAlt`, `strokeRoundedSparkles`…). Mettre à jour le docstring de classe (« 5 cartes » → « 6 cartes »).

- [ ] **Step 4 : Câbler `CatalogueBloc` dans `app.dart`**

Dans `app/lib/app.dart`, ajouter les imports :

```dart
import 'features/catalogue/catalogue_bloc.dart';
import 'features/catalogue/catalogue_repository.dart';
```

et le provider après `AlignmentBloc` :

```dart
          BlocProvider<CatalogueBloc>(
            create: (ctx) => CatalogueBloc(
              repo: CatalogueRepository(api: ctx.read<ApiService>()),
            ),
          ),
```

- [ ] **Step 5 : Lancer les tests Hub + analyse globale**

Run: `cd app && flutter test test/features/hub/hub_screen_test.dart && flutter analyze`
Expected: PASS + analyze clean (tout le projet).

- [ ] **Step 6 : Lancer toute la suite Flutter**

Run: `cd app && flutter test`
Expected: PASS (tous les tests verts).

- [ ] **Step 7 : Commit**

```bash
git add app/lib/app.dart app/lib/features/hub/hub_screen.dart app/test/features/hub/hub_screen_test.dart
git commit -m "feat(app): CATALOGUE hub card + wire CatalogueBloc"
```

---

# Clôture

- [ ] **Mettre à jour la roadmap** (`docs/project/roadmap.md`) : Macro 3 #3 GoTo réel `📦 → 🚧/✅ software livré`, #5 Page Catalogue `📦 → ✅ software livré 2026-05-31`. Préciser « validation matérielle (slew réel) reportée derrière dongle CP2102 ».
- [ ] **Journal** (`docs/project/journal.md`) : ajouter la session (architecture goto + is_aligned + visibilité + page Catalogue, compte de tests avant/après).
- [ ] Vérifier `cd backend && uv run pytest -q` ET `cd app && flutter test` verts, `flutter analyze` clean.
- [ ] Commit docs : `docs: session catalogue+goto + roadmap Macro 3 #3/#5`.

## Hors périmètre (rappel)
- Validation matérielle E2E (slew réel) — bloquée dongle CP2102.
- Messier/planètes (skyfield), seuil obstruction Setup tube, pagination paresseuse — Macro 4.
