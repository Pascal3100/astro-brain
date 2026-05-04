# v0.2 Setup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Date** : 2026-05-04
> **Spec** : [docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md](../specs/2026-05-01-astro-brain-v02-setup-design.md)
> **Statut** : prêt à exécution (Slices A/B/C). Slice D bloquée tant que le dongle CP2102 n'est pas livré + Task 14 du plan migration INDI verte.
> **Plan amont (déjà exécuté)** : [2026-05-03-v02-setup-scaffold-network.md](2026-05-03-v02-setup-scaffold-network.md) — scaffold UI 9 cartes + item #8 Network.
> **Plan amont (déjà exécuté)** : [2026-05-01-mount-indi-migration.md](2026-05-01-mount-indi-migration.md) — `MountIndiAdapter`, cordwrap, backlash adapter-side.

**Goal :** livrer les 7 items Setup restants de la spec v0.2 (#1 niveau monture, #2 compass, #3 zéro ALT, #4 courses ALT, #5 backlash ALT, #6 backlash AZ, #7 cordwrap, #9 about), tout en mettant en place l'infra backend manquante (SQLite persistance, services calibration, adapters I2C, sensor SSE streams).

**Architecture :** ajout d'un module persistance (`repository/state_db.py` + `migrations/`), d'un service `calibration` (state machine `idle → sampling → computing → done|aborted`, single-session global), de deux adapters I2C (`lis3mdl_adapter`, `adxl345_adapter`), de quatre routers (`calibration`, `limits`, `mount_tuning`, `sensors`, `about`), et de 6 sous-écrans Flutter (un par item non-réseau) + 2 stream services (`TiltStreamService`, `CompassStreamService`). Le bus système v0.1 reste inchangé.

**Tech Stack :** Python 3.13, FastAPI, `aiosqlite` (nouveau), `smbus2` (nouveau, optional dep `[hardware]`), `numpy` (nouveau, calc ellipsoid fit), `pyindi-client` (existant), pytest. Flutter, `flutter_bloc`, `equatable`, `phosphor_flutter`, `http`. Tests : `pytest`/`pytest-asyncio` + `flutter_test`/`bloc_test`.

---

## Spec deltas vs INDI migration

La spec v0.2 (datée 2026-05-01, **avant** l'atterrissage de la migration INDI Session 16) doit être lue avec ces corrections :

- **Items #5/#6/#7 → `MountIndiAdapter`, pas `nexstar_adapter`.** La migration a supprimé `nexstar_adapter.py`. Les méthodes consommées par les routes `/mount/tuning/*` existent déjà sur `MountIndiAdapter` : `set_backlash`, `get_backlash`, `cordwrap_set_enabled`, `cordwrap_get_enabled`, `cordwrap_set_position`, `cordwrap_get_position`. **Aucun code adapter mount à toucher** — uniquement les routes + UI.
- **Items #5/#6 plage de valeurs : 0..99 (pas 0..255).** L'adapter valide déjà `0 <= value <= 99` (ligne 416 de `mount_indi_adapter.py`). Les routes et le frontend doivent matcher cette borne, conforme au backlash AUX 1-byte non-saturé du driver patché.
- **Cordwrap position = cardinal (`N`/`E`/`S`/`W`), pas un float `position_deg`.** Le driver patché expose `CORDWRAP_POS` switch 1-of-many sur 4 cardinaux ; l'adapter expose déjà cette signature. Update spec API mentale : `PUT /mount/tuning/cordwrap` body `{ enabled: bool, position?: "N"|"E"|"S"|"W" }`.
- **Routes vivent dans `routes/`, pas `routers/`.** Le repo utilise déjà `backend/astro_brain/routes/` (commands.py, state.py, events.py). On suit cette convention pour les 5 nouveaux routers.
- **Le clamp ALT côté backend (spec § Limits) s'applique dans `MountIndiAdapter.slew()`/`goto_*()`** — la primitive `goto_*` n'existe pas en v0.2 (reportée v0.3). En v0.2, on intègre le clamp dans `slew()` uniquement : si `axis="alt"` et `direction="+"` et que la position estimée actuelle ≥ `max_deg - margin`, refuser + log warning. Ce clamp est **best-effort** car la position ALT live n'est pas encore lue côté backend (ADXL345 tube mais pas sur le bus). Le plan livre la lecture des bornes + transmission au mount adapter ; **l'application stricte du clamp est explicitement reportée v0.3** (commenté dans l'adapter avec un TODO référencé). En v0.2, l'utilisateur reste responsable.
- **Heading compass tilt-compensé en v0.2** (décision arbitrée 2026-05-04) — la spec § Sensor live streams expose `heading_deg` sur `/sensors/compass/stream`. v0.2 livre la version **tilt-compensée** : le stream lit ADXL mount + LIS3MDL chaque tick, applique les bias/soft-iron/hard-iron corrigés, dérive pitch/roll de l'accéléromètre, et calcule `heading = atan2(my', mx')` après rotation du vecteur magnétique. Justification : une mise en station nécessite la monture nivelée → l'utilisateur fait toujours item #1 avant utilisation. Soft warning ⚠ sur la carte compass si #1 non calibré ; le stream renvoie un fallback naïve avec `tilt_compensated: false` dans le payload. Pas de blocage dur sur la finalize de la calibration compass — la calib LIS3MDL elle-même n'a pas besoin de l'ADXL (ellipsoid fit sur samples bruts).

---

## Already shipped (do NOT replan)

- ✅ **#8 Réseau** — `NetworkScreen`/`NetworkBloc` + `PiHost.fromPrefs()` + `astro.host` / `astro.port` `SharedPreferences`. Plan amont : `2026-05-03-v02-setup-scaffold-network.md`.
- ✅ **Scaffold SetupScreen** — 9 `SetupCard` listées dans `app/lib/features/setup/setup_screen.dart`. Cartes #1..#7 + #9 sont des placeholders gris cliquables-mais-no-op. **Ce plan les rend interactives.**
- ✅ **AppBar partagée** `AstroAppBar` avec icône engrenage Setup + désactivation par `current=AstroScreen.setup`.
- ✅ **`MountIndiAdapter`** — backlash + cordwrap déjà implémentés et testés. Plan : `2026-05-01-mount-indi-migration.md`.
- ✅ **Smoke test E2E mount sur le Pi** — bloque sur le dongle CP2102, **pas sur ce plan**. Slice D reste indépendamment bloquée par cette livraison hardware.

---

## Stratégie de branches

**Recommandation :** une branche par slice + un PR-merge incrémental. Cela évite une mégabranche v0.2 monolithique, et permet de livrer Slice A en premier (utile et auto-suffisant) pendant que Slices B/C suivent.

| Slice | Branche | Dépend de | Bloqueur hardware ? |
|---|---|---|---|
| Pré-requis backend | `feat/v02-setup-backend-infra` | `main` | non |
| A — Calibrations capteurs (#1, #2, #3) | `feat/v02-setup-sensors` | infra | non |
| B — Courses ALT (#4) | `feat/v02-setup-limits` | A (item #3 + tilt stream) | non |
| C — About (#9) | `feat/v02-setup-about` | infra | non |
| D — Backlash & cordwrap (#5, #6, #7) | `feat/v02-setup-mount-tuning` | infra + Task 14 INDI | **oui** (dongle CP2102) |

Slices A/B/C peuvent tourner en parallèle si on le souhaite (Bloc dispatching), mais comme elles partagent `repository/state_db.py` et `services/calibration.py`, exécuter A complètement avant B est plus simple. Slice D peut être planifiée + reviewée mais **mergée seulement après Task 14 du plan migration INDI**.

**À chaque fin de slice** : merge `--no-ff` dans `main`, lancer `uv run pytest -q` côté backend et `flutter test` côté app, mettre à jour le journal session courante.

---

## File Structure

### Créés (backend)

| Fichier | Slice | Responsabilité |
|---|---|---|
| `backend/astro_brain/repository/__init__.py` | infra | Marqueur package. |
| `backend/astro_brain/repository/state_db.py` | infra | `aiosqlite` connection helper, `get_db()`, run_migrations(). |
| `backend/astro_brain/repository/migrations/__init__.py` | infra | Marqueur. |
| `backend/astro_brain/repository/migrations/_001_initial.py` | infra | Schéma `schema_version`, `calibration_sensor`, `mount_limits`. |
| `backend/astro_brain/repository/calibration_repo.py` | infra | CRUD typé : get/upsert offsets par sensor_id. |
| `backend/astro_brain/repository/limits_repo.py` | infra | CRUD typé sur `mount_limits[alt]`. |
| `backend/astro_brain/models/__init__.py` | infra | Marqueur. |
| `backend/astro_brain/models/calibration.py` | infra | Pydantic : `Lis3mdlOffsets`, `Adxl345Offsets`, `AltLimits`, `CalibrationStatus`, `CalibrationSample`, `CalibrationProgress`. |
| `backend/astro_brain/adapters/lis3mdl_adapter.py` | A | I2C 0x1E, `read_raw() -> (mx, my, mz)` µT, `start()/stop()`. |
| `backend/astro_brain/adapters/adxl345_adapter.py` | A | I2C, factory `mount(0x1D)` / `tube(0x53)`, `read_raw_g()`, `start()/stop()`. |
| `backend/astro_brain/adapters/_i2c_helpers.py` | A | Lazy import `smbus2`, fake-friendly. |
| `backend/astro_brain/services/calibration.py` | A | Single-session orchestrator, state machine, sampling loop. |
| `backend/astro_brain/services/_ellipsoid_fit.py` | A | Pure numpy fit Li-Lawley + coverage discretisation. |
| `backend/astro_brain/services/_bias_fit.py` | A | Pure 3-axis bias mean + sigma. |
| `backend/astro_brain/routes/calibration.py` | A | `/calibration/*`. |
| `backend/astro_brain/routes/sensors.py` | A/B | `/sensors/tilt/stream`, `/sensors/compass/stream`. |
| `backend/astro_brain/routes/limits.py` | B | `/limits/alt`. |
| `backend/astro_brain/routes/mount_tuning.py` | D | `/mount/tuning/*`. |
| `backend/astro_brain/routes/about.py` | C | `/about`. |
| `backend/tests/fakes/fake_i2c.py` | A | `FakeLis3mdl`, `FakeAdxl345` programmables. |
| `backend/tests/test_state_db.py` | infra | Migrations idempotentes, schéma posé. |
| `backend/tests/test_calibration_repo.py` | infra | Upsert + read. |
| `backend/tests/test_limits_repo.py` | infra | idem. |
| `backend/tests/test_lis3mdl_adapter.py` | A | Lecture I2C via fake. |
| `backend/tests/test_adxl345_adapter.py` | A | Lecture I2C via fake, deux adresses. |
| `backend/tests/test_calibration_service.py` | A | State machine, abort, finalize, single-session lock. |
| `backend/tests/test_ellipsoid_fit.py` | A | Fit numérique sur sphère synthétique. |
| `backend/tests/test_calibration_routes.py` | A | REST + SSE. |
| `backend/tests/test_sensors_routes.py` | A | SSE tilt + compass, lazy-open. |
| `backend/tests/test_limits_routes.py` | B | REST. |
| `backend/tests/test_mount_tuning_routes.py` | D | REST + 503 si mount=error. |
| `backend/tests/test_about_route.py` | C | REST + champs présents. |

### Créés (frontend)

| Fichier | Slice | Responsabilité |
|---|---|---|
| `app/lib/services/tilt_stream_service.dart` | A/B | SSE `/sensors/tilt/stream`. |
| `app/lib/services/compass_stream_service.dart` | A | SSE `/sensors/compass/stream`. |
| `app/lib/models/calibration.dart` | A | Models JSON parse pour offsets + progress + status. |
| `app/lib/features/setup/calibration/lis3mdl_screen.dart` | A | Item #2 UI. |
| `app/lib/features/setup/calibration/lis3mdl_bloc.dart` | A | |
| `app/lib/features/setup/calibration/lis3mdl_event.dart` | A | |
| `app/lib/features/setup/calibration/lis3mdl_state.dart` | A | |
| `app/lib/features/setup/calibration/adxl_mount_screen.dart` | A | Item #1 UI. |
| `app/lib/features/setup/calibration/adxl_mount_bloc.dart` | A | |
| `app/lib/features/setup/calibration/adxl_mount_event.dart` | A | |
| `app/lib/features/setup/calibration/adxl_mount_state.dart` | A | |
| `app/lib/features/setup/calibration/adxl_tube_screen.dart` | A | Item #3 UI. |
| `app/lib/features/setup/calibration/adxl_tube_bloc.dart` | A | |
| `app/lib/features/setup/calibration/adxl_tube_event.dart` | A | |
| `app/lib/features/setup/calibration/adxl_tube_state.dart` | A | |
| `app/lib/features/setup/calibration/widgets/calibration_progress.dart` | A | Spinner + pct + sigma + hint. |
| `app/lib/features/setup/limits/limits_screen.dart` | B | Item #4 UI. |
| `app/lib/features/setup/limits/limits_bloc.dart` | B | |
| `app/lib/features/setup/limits/limits_event.dart` | B | |
| `app/lib/features/setup/limits/limits_state.dart` | B | |
| `app/lib/features/setup/about/about_screen.dart` | C | Item #9 UI. |
| `app/lib/features/setup/about/about_bloc.dart` | C | |
| `app/lib/features/setup/about/about_event.dart` | C | |
| `app/lib/features/setup/about/about_state.dart` | C | |
| `app/lib/features/setup/backlash/backlash_screen.dart` | D | Items #5 + #6 UI (param `axis`). |
| `app/lib/features/setup/backlash/backlash_bloc.dart` | D | |
| `app/lib/features/setup/backlash/backlash_event.dart` | D | |
| `app/lib/features/setup/backlash/backlash_state.dart` | D | |
| `app/lib/features/setup/cordwrap/cordwrap_screen.dart` | D | Item #7 UI. |
| `app/lib/features/setup/cordwrap/cordwrap_bloc.dart` | D | |
| `app/lib/features/setup/cordwrap/cordwrap_event.dart` | D | |
| `app/lib/features/setup/cordwrap/cordwrap_state.dart` | D | |
| `app/test/services/tilt_stream_service_test.dart` | A/B | |
| `app/test/services/compass_stream_service_test.dart` | A | |
| `app/test/features/setup/calibration/lis3mdl_bloc_test.dart` | A | |
| `app/test/features/setup/calibration/adxl_mount_bloc_test.dart` | A | |
| `app/test/features/setup/calibration/adxl_tube_bloc_test.dart` | A | |
| `app/test/features/setup/limits/limits_bloc_test.dart` | B | |
| `app/test/features/setup/about/about_bloc_test.dart` | C | |
| `app/test/features/setup/backlash/backlash_bloc_test.dart` | D | |
| `app/test/features/setup/cordwrap/cordwrap_bloc_test.dart` | D | |

### Modifiés

| Fichier | Slice | Changement |
|---|---|---|
| `backend/pyproject.toml` | infra/A | Ajout `aiosqlite>=0.20`, `numpy>=2.0` (core) ; ajout `smbus2>=0.4` (extra `hardware`). |
| `backend/astro_brain/app.py` | infra→D | À chaque slice : enregistrer router + injecter le service correspondant sur `app.state` + initialiser DB dans le lifespan + démarrer adapters I2C en `use_hardware=True`. |
| `backend/astro_brain/deps.py` | infra→D | Ajout `get_db`, `get_calibration_service`, `get_lis3mdl`, `get_adxl_mount`, `get_adxl_tube`. |
| `backend/astro_brain/services/interfaces.py` | A | Ajout protocols `Lis3mdlService`, `Adxl345Service`, `CalibrationService`. |
| `backend/astro_brain/services/fakes.py` | A | Ajout `FakeLis3mdl`, `FakeAdxl345Mount`, `FakeAdxl345Tube` (séquences pré-enregistrées). |
| `backend/deploy/astro-brain.service` | infra | `StateDirectory=astro-brain` + `Environment="ASTRO_BRAIN_STATE_DIR=/var/lib/astro-brain"`. |
| `backend/deploy/install.sh` | infra | Crée `/var/lib/astro-brain` (idempotent ; backup si systemd `StateDirectory` n'a pas encore tourné). |
| `backend/deploy/INTEGRATION_CHECKLIST.md` | infra→D | Ajout section "DB persistante", "Capteurs I2C (LIS3MDL + 2× ADXL345)", "Calibration sessions", "Backlash", "Courses ALT". |
| `app/lib/features/setup/setup_screen.dart` | A→D | À chaque slice : remplacer la carte placeholder par une `SetupCard` cliquable avec sublabel dynamique (lu via REST sur `initState` du `SetupScreen`). |
| `app/lib/services/api_service.dart` | A→C | Helpers `getCalibrationStatus`, `startCalibration`, `finalizeCalibration`, `abortCalibration`, `getLimits`, `putLimits`, `getMountTuning`, `putBacklash`, `putCordwrap`, `getAbout`. |
| `app/lib/main.dart` | A | Pré-instancier `TiltStreamService` + `CompassStreamService` au top-level (dispose dans `MyApp.dispose`). |
| `docs/technical/api.md` | infra→D | Ajout sections complètes : `/calibration/*`, `/limits/alt`, `/mount/tuning/*`, `/sensors/*/stream`, `/about`. |
| `docs/technical/architecture.md` | infra | Diagramme + texte : ajout `aiosqlite` + `state.db` + `repository/`. |
| `docs/technical/state-model.md` | infra | Note : "Calibration n'est pas sur le bus santé v0.2 (lecture REST à la demande)." |
| `docs/project/journal.md` | A→D | Une entrée session par slice livrée. |

---

## Convention TDD par task

Chaque task de ce plan suit le pattern `superpowers:subagent-driven-development` du plan migration INDI :

1. Implementer Sonnet : écrit le test ; le voit échouer ; implémente ; voit passer ; lint.
2. Spec reviewer : valide que la task respecte la spec v0.2 + ce plan.
3. Code-quality reviewer : check style, gestion erreurs, edge cases.
4. Implementer applique les fixes "Important", note les "Minor" en suspens.
5. Commit (un par task, format conventional commits).

Aucune task ne dépasse 3 fichiers / ~200 LOC tests inclus.

---

# Backend infrastructure — Pré-requis (Slice infra)

**Branche :** `feat/v02-setup-backend-infra`. Mergée dans `main` avant Slice A.

## Task INFRA-0 : Préparation — branche, baseline tests, deps

**Files:** Run only.

- [ ] **Step 1** : `git checkout main && git pull && git checkout -b feat/v02-setup-backend-infra`. Working tree clean.
- [ ] **Step 2** : Baseline backend `cd backend && uv run pytest -q`. Note nombre de tests (89 attendu).
- [ ] **Step 3** : Baseline app `cd app && flutter test`. Note nombre.
- [ ] **Step 4** : Modifier `backend/pyproject.toml` :
  - Ajouter `aiosqlite>=0.20` aux `dependencies` (core).
  - Ajouter `numpy>=2.0` aux `dependencies` (core — utilisé par `_ellipsoid_fit.py` et `_bias_fit.py`).
  - Ajouter `smbus2>=0.4` à l'extra `hardware`.
- [ ] **Step 5** : `uv lock && uv sync` ; vérifier que tests passent toujours.
- [ ] **Step 6** : Commit `chore(backend): add aiosqlite, numpy core + smbus2 hardware deps for v0.2 Setup`.

## Task INFRA-1 : Pydantic models calibration

**Files:**
- Create: `backend/astro_brain/models/__init__.py`
- Create: `backend/astro_brain/models/calibration.py`
- Create: `backend/tests/test_models_calibration.py`

Modèles plats, sérialisables JSON, sans logique. Servent à la fois pour le repo (payload_json) et pour les routes Pydantic.

**Modèles à livrer :**
- `Adxl345Offsets(bias: tuple[float, float, float], sigma: float, zero_alt_deg: float | None = None)` — `zero_alt_deg` non-None pour le tube uniquement.
- `Lis3mdlOffsets(offsets: tuple[float, float, float], scale_matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]], coverage_pct: float, residual: float)`.
- `AltLimits(min_deg: float, max_deg: float)` avec validateur `min_deg < max_deg` et `(max_deg - min_deg) >= 30`.
- `CalibrationProgress(state: Literal["idle","sampling","computing","done","aborted","error"], samples_n: int, coverage_pct: float, sigma: float, hint: str | None, residual: float | None = None)`.
- `CalibrationStatus(sensor_id: str, calibrated_at: datetime | None, payload: Adxl345Offsets | Lis3mdlOffsets | None)`.

**Tests :** parse + serialize round-trip pour chacun ; rejet validation `AltLimits` `(20, 25)` car écart < 30°.

**Steps :** test fail → implémentation → test pass → ruff → commit `feat(backend): pydantic models for calibration payloads`.

## Task INFRA-2 : `repository/state_db.py` + migration runner

**Files:**
- Create: `backend/astro_brain/repository/__init__.py`
- Create: `backend/astro_brain/repository/state_db.py`
- Create: `backend/astro_brain/repository/migrations/__init__.py`
- Create: `backend/astro_brain/repository/migrations/_001_initial.py`
- Create: `backend/tests/test_state_db.py`

**API attendue de `state_db.py` :**

```python
DB_FILENAME = "state.db"
STATE_DIR_ENV = "ASTRO_BRAIN_STATE_DIR"
STATE_DIR_DEFAULT = "/var/lib/astro-brain"

def db_path() -> Path: ...  # honors STATE_DIR_ENV, mkdir parents=True
@asynccontextmanager
async def get_db(path: Path | None = None) -> AsyncIterator[aiosqlite.Connection]: ...
async def run_migrations(db: aiosqlite.Connection) -> int: ...  # returns version applied
```

`run_migrations` lit `migrations/_NNN_*.py`, importe par ordre, applique celles dont `version > schema_version[0]`, dans une transaction par migration. Idempotent.

**Migration `_001_initial.py` :**
```python
VERSION = 1
SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calibration_sensor (
  sensor_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  calibrated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mount_limits (
  axis TEXT PRIMARY KEY,
  min_deg REAL NOT NULL,
  max_deg REAL NOT NULL,
  set_at TEXT NOT NULL
);
"""
```

**Tests** (`tests/test_state_db.py`, all using `:memory:` via `aiosqlite.connect(":memory:")` in a fixture) :
- `test_run_migrations_creates_schema` — version=1 après run, tables existent.
- `test_run_migrations_is_idempotent` — second run = no-op (renvoie 1, schéma intact).
- `test_db_path_honors_env` — set `ASTRO_BRAIN_STATE_DIR=tmp_path`, vérif `db_path()` retourne `tmp_path/state.db`.

**Steps :** test fail → impl `state_db.py` + `_001` → test pass → ruff → commit `feat(backend): aiosqlite repository scaffolding + initial migration`.

## Task INFRA-3 : `calibration_repo.py` (CRUD typé sur `calibration_sensor`)

**Files:**
- Create: `backend/astro_brain/repository/calibration_repo.py`
- Create: `backend/tests/test_calibration_repo.py`

**API :**
```python
SENSOR_IDS = frozenset({"lis3mdl", "adxl345_mount", "adxl345_tube"})

async def get_offsets(db, sensor_id: str) -> CalibrationStatus: ...  # 404→payload=None, calibrated_at=None
async def upsert_offsets(db, sensor_id: str, payload: Adxl345Offsets | Lis3mdlOffsets) -> None: ...
```

`upsert_offsets` valide que `sensor_id ∈ SENSOR_IDS` (sinon `ValueError`), valide que payload est cohérent avec sensor_id (lis3mdl→Lis3mdlOffsets, adxl→Adxl345Offsets), sérialise en JSON via `model_dump_json()`, écrit avec `INSERT...ON CONFLICT(sensor_id) DO UPDATE`. `calibrated_at` = `datetime.now(UTC).isoformat()`.

**Tests :** upsert puis get round-trip pour les 3 sensors ; validation cross-type rejette `lis3mdl` avec `Adxl345Offsets`. Tests utilisent une fixture `db` `:memory:` qui run les migrations.

**Steps :** TDD standard, commit `feat(backend): calibration_sensor repository (typed CRUD)`.

## Task INFRA-4 : `limits_repo.py`

**Files:**
- Create: `backend/astro_brain/repository/limits_repo.py`
- Create: `backend/tests/test_limits_repo.py`

**API :**
```python
async def get_alt_limits(db) -> AltLimits | None: ...  # None si jamais set
async def set_alt_limits(db, limits: AltLimits) -> None: ...
```

`set_alt_limits` upsert sur `axis="alt"`, valide la cohérence via le validator Pydantic (déjà fait à la construction).

**Tests :** None initial → set → get retourne valeurs ; second set overwrites.

**Steps :** TDD standard, commit `feat(backend): mount_limits repository (typed CRUD)`.

## Task INFRA-5 : Wire DB lifecycle dans `app.py`

**Files:**
- Modify: `backend/astro_brain/app.py`
- Modify: `backend/astro_brain/deps.py`
- Modify: `backend/tests/test_app.py` (ou nouveau test)

Ajouter dans le `lifespan` de `build_app` :
- Au startup : `db = await aiosqlite.connect(db_path()); await run_migrations(db); app.state.db = db`.
- Au shutdown : `await db.close()`.

Pour les tests : permettre `build_app(use_hardware=False, db_path=":memory:")` (paramètre supplémentaire) qui pose une DB éphémère partagée pour la durée de l'app. La signature publique de `build_app` reste rétro-compatible.

Ajouter dans `deps.py` :
```python
def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db
```

**Tests :** `test_app_initializes_db` — build_app, lifespan, vérifier `app.state.db` connecté + `schema_version` à 1.

**Steps :** test fail → impl → test pass → 89 + delta tests verts → ruff → commit `feat(backend): wire aiosqlite DB into FastAPI lifespan`.

## Task INFRA-6 : Systemd `StateDirectory=astro-brain`

**Files:**
- Modify: `backend/deploy/astro-brain.service`
- Modify: `backend/deploy/install.sh`
- Modify: `backend/deploy/INTEGRATION_CHECKLIST.md`

`astro-brain.service` :
```ini
[Service]
StateDirectory=astro-brain
StateDirectoryMode=0750
Environment="ASTRO_BRAIN_STATE_DIR=/var/lib/astro-brain"
# (le reste inchangé)
```

`install.sh` : pas de création manuelle de `/var/lib/astro-brain` requise (`StateDirectory` le gère). Ajouter un `mkdir -p` idempotent en backup pour les contextes test sans systemd. Rendre `chown $USER:$USER` conditionnel (skip si déjà owned).

`INTEGRATION_CHECKLIST.md` : ajouter section **"DB persistante"** :
- [ ] Après `bash deploy/install.sh`, `ls -la /var/lib/astro-brain/` montre `state.db` créé par astro-brain.service à son premier startup.
- [ ] `sqlite3 /var/lib/astro-brain/state.db ".schema"` retourne les 3 tables (`schema_version`, `calibration_sensor`, `mount_limits`).
- [ ] `sqlite3 /var/lib/astro-brain/state.db "SELECT * FROM schema_version;"` → version=1.

**Tests :** pas de test automatisé pour systemd ; visuel + checklist.

**Steps :** edit + commit `deploy: add StateDirectory=astro-brain for sqlite state.db`.

## Task INFRA-7 : Mise à jour doc architecture

**Files:**
- Modify: `docs/technical/architecture.md`
- Modify: `docs/technical/state-model.md`

Ajouter `aiosqlite` + `state.db` dans le diagramme. Ajouter dans state-model.md une note explicite :

> Calibration et limits **ne sont pas sur le bus santé** v0.2. Lecture à la demande via REST. Le bus santé reste sur 5 subsystems (mount, gps, tracking, network, system).

**Steps :** edit + commit `docs: architecture + state-model — sqlite state.db + calibration off-bus`.

**End of Slice infra : `git checkout main && git merge --no-ff feat/v02-setup-backend-infra`.**

---

# Slice A — Calibrations capteurs (#1, #2, #3)

**Branche :** `feat/v02-setup-sensors`. Bloque #4. Pas de hardware bloqueur (capteurs I2C indépendants de la monture).

Le code suit cette progression : adapters I2C → service calibration → routes REST/SSE → frontend par item.

## Task A-1 : `adapters/_i2c_helpers.py` — lazy import smbus2 + fake mode

**Files:**
- Create: `backend/astro_brain/adapters/_i2c_helpers.py`
- Create: `backend/tests/test_i2c_helpers.py`

Pure helper. Lazy import de `smbus2`. Si `ASTRO_BRAIN_HARDWARE != "1"`, retourne un fake stub. Centralise `read_bytes(bus, addr, reg, n)` pour les deux adapters I2C.

**API :**
```python
def open_bus(bus_number: int = 1) -> Any: ...   # returns smbus2.SMBus or stub
def read_bytes(bus: Any, addr: int, reg: int, n: int) -> bytes: ...
def write_byte(bus: Any, addr: int, reg: int, value: int) -> None: ...
```

**Tests :** stub mode, mock `smbus2`, write+read round-trip.

**Steps :** TDD standard, commit `feat(backend): i2c helpers (lazy smbus2 import + fake stub)`.

## Task A-2 : `adapters/lis3mdl_adapter.py`

**Files:**
- Create: `backend/astro_brain/adapters/lis3mdl_adapter.py`
- Create: `backend/tests/test_lis3mdl_adapter.py`
- Modify: `backend/tests/fakes/fake_i2c.py` (créer aussi)

**API :**
```python
LIS3MDL_I2C_ADDR = 0x1E

class Lis3mdlAdapter:
    def __init__(self, *, bus_number: int = 1, addr: int = LIS3MDL_I2C_ADDR, fake: Any | None = None) -> None: ...
    async def start(self) -> None: ...   # config registers : ODR=80Hz, FS=±4 gauss, continuous conversion
    async def stop(self) -> None: ...    # power-down mode
    async def read_raw(self) -> tuple[float, float, float]: ...  # µT, no calibration applied
```

Sequence init (depuis datasheet ST LIS3MDL, à confirmer via reviewer hardware) :
- CTRL_REG1 (0x20) = 0x70 (ultra-high perf XY, 80 Hz, temp off)
- CTRL_REG2 (0x21) = 0x00 (FS = ±4 gauss → 6842 LSB/gauss)
- CTRL_REG3 (0x22) = 0x00 (continuous conversion)
- CTRL_REG4 (0x23) = 0x0C (ultra-high perf Z)
- BLE = LE, mode `OUT_X_L` 0x28 + auto-increment.

`read_raw()` lit 6 bytes à `0x28 | 0x80`, parse little-endian signed int16 × 3, convertit en µT (`raw / 6842.0 * 100` en µT).

**Tests** (avec fake `FakeLis3mdl` qui pré-load des registres ou retourne directement une séquence) :
- `test_start_writes_init_sequence` — vérifie les writes CTRL_REG1..4.
- `test_read_raw_parses_signed_int16_le` — fake registers programmés à des valeurs connues, vérif tuple.
- `test_stop_powers_down` — CTRL_REG3 mis à `0x03` (power down).

**Risque :** la séquence init est une hypothèse à valider physiquement (cf. Risks section). Le reviewer doit insister sur "TODO confirmer registres avant smoke test #2".

**Steps :** TDD standard, commit `feat(backend): LIS3MDL I2C adapter (raw mag readings)`.

## Task A-3 : `adapters/adxl345_adapter.py`

**Files:**
- Create: `backend/astro_brain/adapters/adxl345_adapter.py`
- Create: `backend/tests/test_adxl345_adapter.py`
- Modify: `backend/tests/fakes/fake_i2c.py`

**API :**
```python
ADXL345_TUBE_ADDR = 0x53     # SDO/ALT à GND
ADXL345_MOUNT_ADDR = 0x1D    # SDO/ALT à VDD

class Adxl345Adapter:
    def __init__(self, *, bus_number: int = 1, addr: int, fake: Any | None = None) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def read_raw_g(self) -> tuple[float, float, float]: ...  # g, raw uncalibrated

def mount_adapter(*, fake: Any | None = None) -> Adxl345Adapter: ...
def tube_adapter(*, fake: Any | None = None) -> Adxl345Adapter: ...
```

Init datasheet ADI ADXL345 :
- POWER_CTL (0x2D) = 0x08 (measure mode).
- DATA_FORMAT (0x31) = 0x0B (full-resolution, ±16 g, FULL_RES → 4 mg/LSB).
- BW_RATE (0x2C) = 0x0A (100 Hz output rate).

`read_raw_g()` lit 6 bytes à `0x32`, parse signed int16 × 3, convertit en `g` via `raw * 0.004`.

**Tests :** identiques au LIS3MDL, deux instances (mount + tube), adresses différentes ; assertion sur les writes init.

**Risque :** registres init à valider. Fait identique pour les deux capteurs (ce sont deux instances du même chip).

**Steps :** TDD standard, commit `feat(backend): ADXL345 I2C adapter (mount + tube factories)`.

## Task A-4 : `_bias_fit.py` (pure numpy)

**Files:**
- Create: `backend/astro_brain/services/_bias_fit.py`
- Create: `backend/tests/test_bias_fit.py`

```python
def compute_bias_and_sigma(samples: list[tuple[float, float, float]]) -> tuple[tuple[float, float, float], float]:
    """Compute 3D mean bias + max axis sigma for an immobile-sensor dataset.

    Returns (bias, sigma) where sigma is the max stddev across axes (g).
    """
```

Implémentation : `np.array(samples)` → `mean(axis=0)`, `std(axis=0).max()`.

**Tests :** dataset synthétique [(1.0, 0.0, 0.0)] × 100 → bias ≈ (1, 0, 0), sigma ≈ 0. Dataset bruité → sigma > 0.01.

**Steps :** TDD standard, commit `feat(backend): bias+sigma fit for ADXL345 calibration`.

## Task A-5 : `_ellipsoid_fit.py` (pure numpy, Li-Lawley simplifié)

**Files:**
- Create: `backend/astro_brain/services/_ellipsoid_fit.py`
- Create: `backend/tests/test_ellipsoid_fit.py`

**API :**
```python
def compute_ellipsoid_offsets(samples: list[tuple[float, float, float]]) -> tuple[
    tuple[float, float, float],         # offsets (hard-iron, µT)
    tuple[tuple[float, float, float], ...],  # 3x3 scale matrix (soft-iron correction)
    float,                              # residual (mean abs error after applying)
]: ...

def coverage_pct(samples: list[tuple[float, float, float]], n_quadrants: int = 8) -> float:
    """Discretise samples on the unit sphere into `n_quadrants^3` cells (or 8 octants)
    and return % of cells visited. 100 % = full sphere coverage."""
```

Algo retenu : **Li-Lawley** (least-squares fit d'une quadric `ax² + by² + cz² + 2dxy + 2exz + 2fyz + 2gx + 2hy + 2iz = 1`). Résolution analytique via SVD : `np.linalg.lstsq` sur le design matrix. Centre = `inv(A) @ -b/2`. Scale = décomposition de A.

Pour l'algo détaillé : utiliser une référence publique simple (par ex. https://teslabs.com/articles/magnetometer-calibration/ — implémentation Python ~50 LOC). Le reviewer doit valider que l'implémentation correspond à l'algo prévu (pas une heuristique fait-maison).

**Tests :**
- `test_fit_unit_sphere_centered_at_origin` — 200 samples sur sphère parfaite centrée → offsets ≈ (0, 0, 0), scale ≈ I, residual < 0.01.
- `test_fit_offset_sphere` — 200 samples sphère centrée à `(5, 3, -2)`, rayon 1 → offsets ≈ `(5, 3, -2)`.
- `test_fit_ellipsoid_scaled` — sphère étirée par 1.5× sur Z → scale matrix corrige.
- `test_coverage_full_sphere_returns_100` — sphère uniforme → ≥ 95 %.
- `test_coverage_half_sphere_returns_50ish` — hemisphere uniforme → ~50 %.

**Steps :** TDD ; le reviewer "spec" doit demander le pseudo-code lu dans la référence avant approval. Commit `feat(backend): ellipsoid fit (hard-iron + soft-iron) for LIS3MDL calibration`.

## Task A-5b : `_tilt_compensated_heading.py` (pure numpy)

**Files:**
- Create: `backend/astro_brain/services/_tilt_compensated_heading.py`
- Create: `backend/tests/test_tilt_compensated_heading.py`

**API :**
```python
def tilt_compensated_heading(
    mag_corrected: tuple[float, float, float],   # mag après hard/soft-iron correction (µT)
    accel_corrected: tuple[float, float, float], # ADXL mount après bias correction (g)
) -> float:
    """Renvoie le heading magnétique en degrés [0, 360), corrigé pour le tilt
    de la base via le vecteur gravité de l'ADXL co-localisé sur la monture.

    Algo standard :
        pitch = atan2(-ax, sqrt(ay² + az²))
        roll  = atan2(ay, az)
        mx' = mx*cos(pitch) + mz*sin(pitch)
        my' = mx*sin(roll)*sin(pitch) + my*cos(roll) - mz*sin(roll)*cos(pitch)
        heading = atan2(-my', mx')   (convention boussole : nord magnétique = 0°, est = 90°)
    """

def naive_heading(mag_corrected: tuple[float, float, float]) -> float:
    """Fallback sans tilt comp (`atan2(my, mx)`), utilisé quand ADXL mount non calibré."""
```

Convention : `+x` du LIS3MDL pointe nord magnétique du capteur, retour normalisé à `[0, 360)`. Sortie en degrés.

**Tests :**
- `test_naive_heading_north_is_zero` — `(1, 0, 0)` → 0°.
- `test_naive_heading_east_is_90` — `(0, 1, 0)` → 90°.
- `test_naive_heading_west_is_270` — `(0, -1, 0)` → 270°.
- `test_tilt_comp_zero_tilt_matches_naive` — accel pur Z (`(0, 0, 1)`) → tilt-compensated == naïve pour les 4 cardinaux.
- `test_tilt_comp_5deg_pitch_recovers_heading` — appliquer une rotation pitch de 5° au vecteur magnétique d'un nord vrai, fournir l'accel correspondant, vérifier que tilt-compensated retourne 0° (±0.1°). Sans tilt-comp, le heading naïf dévierait.
- `test_tilt_comp_10deg_roll_recovers_heading` — équivalent en roll.
- `test_heading_normalized_to_0_360_range` — tous les retours sont dans `[0, 360)`, pas de négatifs.

**Steps :** TDD ; pure numpy, zero I/O, zero state. Commit `feat(backend): tilt-compensated heading helper (LIS3MDL + ADXL mount)`.

## Task A-6 : `services/calibration.py` — state machine + sampling loop

**Files:**
- Create: `backend/astro_brain/services/calibration.py`
- Modify: `backend/astro_brain/services/interfaces.py`
- Create: `backend/tests/test_calibration_service.py`

**Interface (`interfaces.py` ajouts) :**
```python
class CalibrationService(Protocol):
    async def start(self, sensor_id: str) -> str: ...        # returns session_id
    async def progress(self, session_id: str) -> AsyncIterator[CalibrationProgress]: ...
    async def finalize(self, session_id: str) -> CalibrationStatus: ...
    async def abort(self, session_id: str) -> None: ...
    async def current_session(self) -> tuple[str, str] | None: ...  # (session_id, sensor_id) | None
```

**Service singleton (un par app), state machine :**

```
idle ──start(sensor_id)──→ sampling ──[enough_samples + threshold met]──→ computing
                              ↑                                           │
                              └────[/abort]────────── idle ←──────────────┘
                                                       ↑
                                                       │
                                                       └──finalize→done (writes DB)
```

**Sampling loops :**
- ADXL345 (mount ou tube) : lit `read_raw_g()` toutes les 20 ms (50 Hz), accumule dans une `list[tuple]`. Auto-validation après 100 samples si `sigma < 0.05 g`. Hint :
  - 0..20 samples : "Maintenir immobile".
  - 20..100 + sigma trop haut : "Réduire les vibrations".
  - sigma OK : "Prêt à valider".
- LIS3MDL : lit `read_raw()` toutes les 20 ms (50 Hz), accumule. Auto-validation après 500 samples si `coverage_pct >= 80`. Hint :
  - "Tournez le module dans toutes les directions".
  - coverage 30 %..80 % : "Continuez les rotations".
  - ≥ 80 % : "Couverture suffisante, validez".

**Single-session lock :** un seul `_current_session` actif. `start` lève `ConflictError` si une session est déjà active (mappée à HTTP 409).

**SSE source :** `progress(session_id)` est un générateur async qui yield un `CalibrationProgress` toutes les 200 ms tant que la session existe et que le client n'est pas disconnecté (vérification via task cancellation côté router).

**Tests :**
- `test_start_creates_session` (avec fake adapter qui retourne séquences pré-enregistrées).
- `test_concurrent_start_raises_conflict`.
- `test_progress_emits_state_updates`.
- `test_finalize_writes_to_db_and_clears_session` (assert via `calibration_repo.get_offsets`).
- `test_abort_resets_to_idle_without_writing_db`.
- `test_finalize_before_threshold_raises` (sigma trop haut → 422).
- `test_lis3mdl_coverage_threshold` — fake produit 500 samples sur hémisphère seulement → finalize raises (coverage < 80).

**Risque ouvert :** que se passe-t-il si le client SSE `disconnect` mid-sampling ? Décision : **la session reste active**. Un `start` ultérieur retournera 409 jusqu'à `abort` explicite ou `finalize`. Documenté dans la docstring du service. Voir Risks section.

**Steps :** TDD progressif ; commit `feat(backend): calibration service (state machine + sampling + persistence)`.

## Task A-7 : `routes/calibration.py`

**Files:**
- Create: `backend/astro_brain/routes/calibration.py`
- Create: `backend/tests/test_calibration_routes.py`
- Modify: `backend/astro_brain/app.py` (register router + injecter le service)
- Modify: `backend/astro_brain/deps.py` (ajout `get_calibration_service`)

Endpoints (cf. spec § "Calibration sessions") :
- `POST /calibration/{sensor_id}/start` → 202 `{ session_id }`. 409 si session active. 400 si sensor_id invalide.
- `GET /calibration/{sensor_id}/stream` → SSE `CalibrationProgress` (sse-starlette comme `/events`).
- `POST /calibration/{sensor_id}/finalize` → 200 `CalibrationStatus`. 422 si seuils non atteints. 404 si pas de session active sur ce sensor_id.
- `POST /calibration/{sensor_id}/abort` → 200 `{ ok: true }`.
- `GET /calibration/{sensor_id}` → 200 `CalibrationStatus`. `payload=null` + `calibrated_at=null` si jamais calibré (pas 404 — UI sait gérer).

**Tests :**
- Round-trip POST start → SSE → POST finalize → GET status retourne le calibrated_at.
- 409 lors de start concurrent.
- Sensor_id invalide → 400.
- SSE ferme propre quand session abortée.

**Steps :** TDD ; commit `feat(backend): /calibration REST + SSE routes`.

## Task A-8 : `routes/sensors.py` — tilt + compass SSE streams (lazy)

**Files:**
- Create: `backend/astro_brain/routes/sensors.py`
- Create: `backend/tests/test_sensors_routes.py`
- Modify: `backend/astro_brain/app.py`
- Modify: `backend/astro_brain/deps.py`

Endpoints :
- `GET /sensors/tilt/stream?hz=5` → SSE `{ ts, pitch_deg, roll_deg, magnitude_g }` à `hz` Hz (1..10, clamp). Lit ADXL345 **tube** + applique offsets persistés (s'ils existent — sinon raw + flag `calibrated: false`).
- `GET /sensors/compass/stream?hz=5` → SSE `{ ts, heading_deg, magnitude_uT, raw: {x, y, z}, tilt_compensated: bool, calibrated: bool }`. Lit LIS3MDL + ADXL **mount** chaque tick + applique les offsets persistés.

**Tilt computation** (tilt stream) : `pitch_deg = atan2(-x, sqrt(y² + z²)) * 180/π`, `roll_deg = atan2(y, z) * 180/π`. Magnitude = `sqrt(x² + y² + z²)`.

**Heading computation** (compass stream) — **tilt-compensé en v0.2** (cf. Spec deltas) :
- Toujours : appliquer hard-iron + soft-iron au LIS3MDL.
- Si ADXL **mount** calibré (offsets bias en DB) : appliquer bias, puis `tilt_compensated_heading()` (Task A-5b). Payload : `tilt_compensated: true`.
- Si ADXL mount pas calibré : `naive_heading()` sur le mag corrigé. Payload : `tilt_compensated: false` (UI affiche un warning visible).
- Si LIS3MDL pas calibré : on stream quand même mais `calibrated: false`. Heading présent mais possiblement faux de plusieurs dizaines de degrés ; UI doit le rendre visible.

Le helper `tilt_compensated_heading` est testé en pure numpy dans Task A-5b. Ici, A-8 wire les lectures live ADXL mount + LIS3MDL et l'application des offsets DB.

**Lazy-open** : route ne pomp les capteurs que tant qu'au moins un client SSE écoute. Implémenté côté adapter via `start()` au premier client, `stop()` quand plus de subscriber. Compteur d'abonnés dans le router (ou dans un wrapper service `SensorStreamHub`).

**Tests :**
- `test_tilt_stream_emits_at_5hz` — fake ADXL fournit séquence, SSE retourne 5 samples en 1 seconde.
- `test_tilt_stream_applies_persisted_offsets` — DB pré-loaded avec offsets → samples retournent valeurs calibrées.
- `test_compass_stream_includes_calibrated_flag`.
- `test_hz_clamped_to_1_10`.

**Steps :** TDD ; commit `feat(backend): /sensors/tilt + /sensors/compass SSE streams (lazy)`.

## Task A-9 : Frontend — `models/calibration.dart` + `services/api_service.dart` (extensions)

**Files:**
- Create: `app/lib/models/calibration.dart`
- Modify: `app/lib/services/api_service.dart`
- Create: `app/test/models/calibration_test.dart`
- Create: `app/test/services/api_service_test.dart` (s'il n'existe pas)

Models Dart `equatable` mirrors des Pydantic backend : `Adxl345Offsets`, `Lis3mdlOffsets`, `CalibrationProgress`, `CalibrationStatus`.

`api_service.dart` ajoute :
```dart
Future<CalibrationStatus> getCalibrationStatus(String sensorId);
Future<String> startCalibration(String sensorId);  // returns session_id
Future<CalibrationStatus> finalizeCalibration(String sensorId);
Future<void> abortCalibration(String sensorId);
```

**Tests :** parse JSON synth pour chaque modèle ; mock `http.Client` pour valider URL + headers + parsing.

**Steps :** TDD ; commit `feat(app): calibration models + api service helpers`.

## Task A-10 : Frontend — `TiltStreamService` + `CompassStreamService`

**Files:**
- Create: `app/lib/services/tilt_stream_service.dart`
- Create: `app/lib/services/compass_stream_service.dart`
- Create: `app/test/services/tilt_stream_service_test.dart`
- Create: `app/test/services/compass_stream_service_test.dart`

Inspiration **directe** : `event_stream_service.dart` (réutilise le même pattern de back-off + start/stop/dispose). Différences :
- Pas de "snapshot" / "update" : chaque event SSE est un payload JSON à parser en `TiltReading` ou `CompassReading`.
- L'URL inclut un `?hz=` configurable au constructeur.
- Pas de bus interne — juste un `Stream<TiltReading>` broadcast.

**Modèles :**
```dart
class TiltReading { final DateTime ts; final double pitchDeg, rollDeg, magnitudeG; ... }
class CompassReading { final DateTime ts; final double headingDeg, magnitudeUt; final (double, double, double) raw; final bool calibrated; ... }
```

**Tests :** réutilise les helpers SSE de `event_stream_service_test.dart` (mock http server). Test happy + reconnect.

**Steps :** TDD ; commit `feat(app): tilt + compass SSE stream services`.

## Task A-11 : Frontend — sous-écran #1 ADXL Mount (niveau monture)

**Files:**
- Create: `app/lib/features/setup/calibration/adxl_mount_screen.dart`
- Create: `app/lib/features/setup/calibration/adxl_mount_bloc.dart`
- Create: `app/lib/features/setup/calibration/adxl_mount_event.dart`
- Create: `app/lib/features/setup/calibration/adxl_mount_state.dart`
- Create: `app/lib/features/setup/calibration/widgets/calibration_progress.dart`
- Create: `app/test/features/setup/calibration/adxl_mount_bloc_test.dart`
- Modify: `app/lib/features/setup/setup_screen.dart` (carte #1 cliquable + sublabel)

UI : titre, instructions ("Posez la monture niveau, immobile"), `CalibrationProgress` widget (spinner + samples_n + sigma + hint), bouton **DÉMARRER** / **VALIDER** (grisé tant que sigma > 0.05 ou samples < 100) / **ANNULER**. Au démarrage, ouvre SSE via api_service.

**Bloc events :**
- `Started` → `POST /calibration/adxl345_mount/start` ; ouvre SSE.
- `ProgressReceived(payload)` → met à jour state.
- `FinalizeRequested` → `POST .../finalize` ; sur succès, popNavigator avec `true` (pour invalider le sublabel parent).
- `AbortRequested` → `POST .../abort`.

**Tests bloc** :
- happy : start → progress * N → finalize → state.calibrated = true.
- abort : start → abort → state.idle.
- error : start → 409 (déjà une session active) → state.error.

**Sublabel parent** : après finalize success, le `SetupScreen` re-fetch `GET /calibration/adxl345_mount` et affiche "Calibré il y a Xs" ou "Non calibré".

**Steps :** TDD ; commit `feat(app): item #1 niveau monture (ADXL345 mount calibration screen)`.

## Task A-12 : Frontend — sous-écran #2 Compass (LIS3MDL)

**Files:**
- Create: 4 files `lis3mdl_*.dart` (screen + bloc + event + state)
- Create: `app/test/features/setup/calibration/lis3mdl_bloc_test.dart`
- Modify: `setup_screen.dart` (carte #2)

Identique à Task A-11 mais :
- `sensor_id = "lis3mdl"`.
- Affiche `coverage_pct` (barre de progression sphérique + texte "couverture 64 %").
- Validation requise : `coverage >= 80` ET `residual < seuil`.
- Hint dynamique : "Tournez le module dans toutes les directions" → "Continuez les rotations" → "Prêt".
- Optionnellement, dome 3D wireframe de `phosphor_flutter` (out-of-scope si trop coûteux ; livrer une simple `LinearProgressIndicator` + "X%" texte).
- **Soft warning ⚠ tilt-compensé** : avant le bouton START, si l'état chargé indique que `adxl345_mount` n'est pas calibré, afficher un bandeau jaune "Niveau monture non calibré — le heading sera moins précis. Recommandé : faire d'abord l'item #1." Pas de blocage dur (la calibration LIS3MDL n'a pas besoin de l'ADXL mount). Lecture de l'état via `GET /calibration/adxl345_mount` au moment du push de l'écran.
- **Preview heading post-finalize** : après finalize success, ouvrir `CompassStreamService` à 5 Hz pour afficher le heading live en bas de l'écran ("Cap actuel : 142° (tilt-compensé)" ou "(naïve — niveau monture non calibré)" selon le flag `tilt_compensated` du payload). Stream fermé à la sortie de l'écran.

**Steps :** TDD ; commit `feat(app): item #2 compass (LIS3MDL calibration screen)`.

## Task A-13 : Frontend — sous-écran #3 ADXL Tube (zéro ALT)

**Files:** identique à A-11, sensor_id = `adxl345_tube`. Le payload retourné inclut `zero_alt_deg` (toujours 0.0 dans cette session — c'est le but : capturer "tube horizontal = 0°").

**Note importante :** ce sous-écran consomme aussi le `TiltStreamService` pour afficher l'angle ALT live au-dessus du bouton VALIDER, en preview ("position courante : 0.4° — quand vous validerez, cette position deviendra le zéro"). Le calcul backend persiste `zero_alt_deg = 0` par convention (le tube est horizontal **par construction au moment du clic VALIDER** ; les futures lectures retranchent simplement `bias`).

**Steps :** TDD ; commit `feat(app): item #3 zéro ALT (ADXL345 tube calibration screen)`.

**End of Slice A : `git checkout main && git merge --no-ff feat/v02-setup-sensors`. Add journal entry.**

---

# Slice B — Courses ALT (#4)

**Branche :** `feat/v02-setup-limits`. Dépend de Slice A (item #3 + tilt stream).

## Task B-1 : `routes/limits.py`

**Files:**
- Create: `backend/astro_brain/routes/limits.py`
- Create: `backend/tests/test_limits_routes.py`
- Modify: `backend/astro_brain/app.py`

Endpoints (spec § Limits) :
- `GET /limits/alt` → 200 `AltLimits` ou 404 si jamais set.
- `PUT /limits/alt` body `AltLimits` → 200. Validations (`min_deg < max_deg`, écart ≥ 30°) déjà dans le model Pydantic.

**Note clamp :** ne pas implémenter le clamp dans `MountIndiAdapter.slew()` en v0.2. Ajouter à la place dans `mount_indi_adapter.py` un commentaire `# TODO v0.3: read alt limits from app.state.db, clamp slew("alt", "+") near max_deg`. Tracking issue mental.

**Tests :** PUT then GET ; PUT invalide (écart < 30) → 422 ; GET seul → 404.

**Steps :** TDD ; commit `feat(backend): /limits/alt REST routes`.

## Task B-2 : Frontend — sous-écran #4 Courses ALT

**Files:**
- Create: 4 files `limits_*.dart`
- Create: `app/test/features/setup/limits/limits_bloc_test.dart`
- Modify: `setup_screen.dart` (carte #4)

UI :
- Stream `TiltStreamService` ouvert → live ALT angle gros affichage.
- Bouton "POINTER LE PLUS BAS" → snapshot ALT_min, dim button to "✓ ALT_min capturé : -3.2°".
- Bouton "POINTER LE PLUS HAUT" → snapshot ALT_max, idem.
- Bouton "ENREGISTRER" (grisé tant que les deux ne sont pas capturés ET `max - min >= 30`) → `PUT /limits/alt`.
- Warning ⚠ inline si écart < 30 : "Plage trop faible. Vérifiez vos pointages."

**Bloc events :**
- `LowerCaptured(altDeg)`.
- `UpperCaptured(altDeg)`.
- `SaveRequested`.
- `Reloaded` (initState : `GET /limits/alt`, pre-fill UI si déjà set).

**Sublabel parent** : "min -5° / max 87°" si set, sinon "Non défini".

**Tests bloc** : capture ordering, reset partiel, save happy, save 422.

**Steps :** TDD ; commit `feat(app): item #4 courses ALT min/max screen`.

**End of Slice B : merge `--no-ff` + journal.**

---

# Slice C — About (#9)

**Branche :** `feat/v02-setup-about`. Dépend de l'infra. Pas de dépendance hardware.

## Task C-1 : `routes/about.py`

**Files:**
- Create: `backend/astro_brain/routes/about.py`
- Create: `backend/tests/test_about_route.py`
- Modify: `backend/astro_brain/app.py`

`GET /about` retourne :
```python
{
  "backend_version": "0.2.0",
  "app_version_seen": null,           # set par l'app au prochain GET via header X-App-Version
  "mount_firmware": null | "X.Y",     # via mount.firmware_version() si exposé sur INDI ; v0.2 = null
  "ip": "192.168.x.x",                # NetworkInfoAdapter snapshot
  "ssid": "fake-wifi",                # idem
  "uptime_s": 12345,
  "started_at": "2026-05-04T20:00:00Z"
}
```

`backend_version` lu depuis `astro_brain.__version__` (à ajouter dans `__init__.py` : `__version__ = "0.2.0"`).
`mount_firmware` : best-effort, si `MountIndiAdapter._device.getText("DRIVER_INFO")` accessible → extract ; sinon null.
`ip`, `ssid` : récup depuis `app.state.network` (cf. `NetworkInfoAdapter` snapshot interne — exposer une méthode `current_snapshot() -> dict`).
`uptime_s` : depuis `SystemInfoAdapter.current_snapshot()`.
`started_at` : `app.state.started_at`, set au lifespan startup.

**Tests :** smoke 200 ; champs présents ; mock `app.state.*`.

**Steps :** TDD ; commit `feat(backend): /about route (versions, network, uptime)`.

## Task C-2 : Frontend — sous-écran #9 À propos

**Files:** 4 files `about_*.dart` + test bloc + setup_screen modif (carte #9 cliquable + dot vert quand chargé).

UI : liste read-only de tuples (label : valeur). Bouton "RAFRAÎCHIR" qui re-fetch.

**Versions à afficher** :
- Backend version (issu de `/about`).
- App version (`PackageInfo.fromPlatform()`).
- Mount firmware (issu de `/about`, fallback "—" si null).
- IP, SSID, uptime, started_at.

**Tests bloc** : load happy, load error.

**Steps :** TDD ; commit `feat(app): item #9 about screen`.

**End of Slice C : merge `--no-ff` + journal.**

---

# Slice D — Backlash & Cordwrap (#5, #6, #7) — DONGLE-BLOCKED

**Branche :** `feat/v02-setup-mount-tuning`. **Bloquée par :** livraison du dongle CP2102 + Task 14 du plan migration INDI verte (smoke E2E mount + driver patché installé). Tant que ces deux conditions ne sont pas remplies, **ne pas merger ce slice dans `main`**. Le backend peut être implémenté + reviewé sur fakes ; la validation E2E vient après.

## Task D-1 : `routes/mount_tuning.py`

**Files:**
- Create: `backend/astro_brain/routes/mount_tuning.py`
- Create: `backend/tests/test_mount_tuning_routes.py`
- Modify: `backend/astro_brain/app.py`

Endpoints (spec § Mount tuning, **corrigés post-INDI**) :
- `GET /mount/tuning` → 200 `{ backlash: { alt: {pos, neg}, az: {pos, neg} }, cordwrap: { enabled, position: "N"|"E"|"S"|"W" } }`. 503 si `mount.state == "error"`.
- `PUT /mount/tuning/backlash/{axis}` body `{ pos: int (0..99), neg: int (0..99) }` → 200. Axis ∈ {alt, az}.
- `PUT /mount/tuning/cordwrap` body `{ enabled: bool, position?: "N"|"E"|"S"|"W" }` → 200.

L'implémentation appelle directement `mount.get_backlash`, `mount.set_backlash`, `mount.cordwrap_*`. **Aucun cache backend** : chaque GET fait 4 reads INDI (ALT_POS, ALT_NEG, AZ_POS, AZ_NEG). Latence acceptable (~50 ms par read selon spec).

**Validation** : `0 <= pos <= 99` et `0 <= neg <= 99` (déjà dans Pydantic body model). Position cordwrap dans le set autorisé.

**Détection mount=error → 503** : lire `app.state.bus.get_full_state().subsystems["mount"].state` ; si `"error"`, retourner 503 avec body `{ detail: "mount in error state" }`.

**Tests** (avec `FakeMount` qui supporte déjà toutes ces méthodes) :
- GET round-trip : set via FakeMount avant requête, GET retourne valeurs.
- PUT backlash 50/30 → GET reflète.
- PUT backlash 100 → 422 (out of range).
- PUT cordwrap toggle on + position E → GET reflète.
- Bus mount=error → GET retourne 503.

**Steps :** TDD ; commit `feat(backend): /mount/tuning REST routes (passe-plat AUX)`.

## Task D-2 : Frontend — sous-écran backlash (#5 + #6 partagent un screen paramétré)

**Files:**
- Create: 4 files `backlash_*.dart`
- Create: `app/test/features/setup/backlash/backlash_bloc_test.dart`
- Modify: `setup_screen.dart` (cartes #5 + #6, paramètre `axis: "alt" | "az"` passé via constructeur)

UI (par axe) :
- Affichage current pos/neg lus via `GET /mount/tuning`.
- Deux sliders 0..99 (pos, neg).
- Bouton "ENREGISTRER" → `PUT /mount/tuning/backlash/{axis}`.
- Section instructions UX :
  - "Pointez une cible terrestre fixe (lampadaire de jour)."
  - "Slew dans une direction. Cliquez 'COMMENCER MESURE'."
  - "Inversez le sens. Cliquez chaque fois que vous voyez la cible bouger."
  - Compteur d'incréments (le bloc compte les clics user et propose une valeur).
- Bouton "PROPOSER VALEUR DEPUIS MESURE" → calcule `count * INCREMENT` (INCREMENT=1, à confirmer empirique au smoke), pre-fill le slider.
- 4 mesures (pos puis neg) — un compteur d'étapes en haut.

**Bloc events :**
- `Loaded` → fetch GET, hydrate sliders.
- `MeasureStepStarted(stepIndex)`.
- `MovementObserved(stepIndex)`.
- `MeasureCompleted(stepIndex)` → propose value.
- `SliderChanged(direction, value)`.
- `SaveRequested`.

**Tests bloc** : load → set slider → save → state savedPos == sliderPos.

**Sublabel parent** : "ALT pos 12 / neg 8" ou "Non réglé" si `backlash` non set en DB (pour ce slice, on lit toujours via REST → toujours présent ; le sublabel reflète juste les valeurs courantes).

**Steps :** TDD ; commit `feat(app): item #5 + #6 backlash ALT/AZ screens (parameterized)`.

## Task D-3 : Frontend — sous-écran cordwrap (#7)

**Files:** 4 files `cordwrap_*.dart` + test bloc + setup_screen modif.

UI :
- Toggle "Cordwrap activé" (Switch).
- 4 boutons radio "Position de référence" : N, E, S, W.
- Bouton "ENREGISTRER".
- Instructions : "Vérifiez que le câble est arrangé pour permettre un tour complet sans toucher d'obstacle."

**Bloc events :** `Loaded`, `EnabledToggled(bool)`, `PositionSelected(String)`, `SaveRequested`.

**Steps :** TDD ; commit `feat(app): item #7 cordwrap screen`.

## Task D-4 : Smoke E2E Slice D (manuel, dongle requis)

**Files:** Run only.

- [ ] Précondition : Task 14 plan migration INDI verte (mount alimentée, dongle branché, driver patché installé, `INTEGRATION_CHECKLIST.md` sections 0+3 cochées).
- [ ] `git push -u origin feat/v02-setup-mount-tuning` ; sur le Pi `git fetch && git checkout feat/v02-setup-mount-tuning && bash deploy/install.sh`.
- [ ] App Flutter (Android phone) : ouvrir Setup → carte #5 → ajuster slider à 15 → ENREGISTRER → revenir, vérifier sublabel "ALT pos 15 / neg X".
- [ ] Dans `INDI Control Panel` (ssh -L 7624:localhost:7624) : vérifier `MOUNT_AXIS_BACKLASH.ALT_POS = 15`.
- [ ] Mesurer effet pratique : pointer cible terrestre, slew + inversion sans backlash → noter incréments perdus ; régler backlash via UI ; refaire mesure → constater amélioration.
- [ ] Idem #6 AZ et #7 cordwrap.
- [ ] Cocher dans `INTEGRATION_CHECKLIST.md` les sections "Backlash" et "Cordwrap" (déjà ajoutées par plan migration, à étendre éventuellement).
- [ ] Mettre à jour journal session correspondante.

**Steps :** déploiement + smoke. Si findings → commit dans la même branche. Merge `--no-ff` une fois la checklist verte.

---

# Final integration

## Task FINAL-1 : Mise à jour `docs/technical/api.md`

Ajouter sections complètes :
- `/calibration/{sensor_id}/start|stream|finalize|abort` + `GET`.
- `/sensors/tilt/stream`, `/sensors/compass/stream`.
- `/limits/alt`.
- `/mount/tuning` + sous-routes.
- `/about`.

Tables req/resp avec exemples JSON. Référencer la spec v0.2.

**Steps :** edit + commit `docs(api): add v0.2 Setup endpoints`.

## Task FINAL-2 : Mise à jour `INTEGRATION_CHECKLIST.md`

Sections ajoutées :
- **DB persistante** (déjà ajoutée Task INFRA-6).
- **Capteurs I2C** :
  - [ ] `i2cdetect -y 1` → `0x1D 0x1E 0x53` visibles.
  - [ ] `curl -N localhost:8000/sensors/tilt/stream?hz=2` → 2 samples/s pendant 5 s.
  - [ ] `curl -N localhost:8000/sensors/compass/stream?hz=2` → idem.
- **Calibration sessions** :
  - [ ] Item #1 dans l'app → start → 100 samples sigma < 0.05 g → finalize → DB persisté.
  - [ ] Item #2 idem avec coverage 80 %.
  - [ ] Item #3 idem.
  - [ ] App offline puis online : sublabel reflète bien la calibration persistée.
- **Courses ALT** : pointer min/max, écart ≥ 30°, save persiste.

**Steps :** edit + commit `docs: add v0.2 Setup smoke checklist sections`.

## Task FINAL-3 : Journal de fin de milestone

Une entrée session par slice livrée (déjà fait au merge de chaque branche). En fin de milestone v0.2 :
- Ajouter une entrée "v0.2 Setup livrée" résumant les 9 items, le nombre de tests (estimation : ~150 backend, ~80 app), les ouvertures vers v0.3 (alignment + GoTo + catalogue).
- Archiver les sessions correspondantes selon convention CLAUDE.md (plafond 5-6 sessions actives).

## Task FINAL-4 : End-to-end test plan (manuel)

Sur le Pi + phone Android, dérouler dans l'ordre :
1. App fresh install → Setup → carte #1 → calibrer niveau monture.
2. Carte #2 → calibrer compass.
3. Carte #3 → calibrer zéro ALT.
4. Carte #4 → courses ALT.
5. Carte #5/#6 → backlash ALT + AZ (avec mont alimentée + dongle).
6. Carte #7 → cordwrap.
7. Carte #8 → réseau (déjà testé Plan amont).
8. Carte #9 → about, vérifier versions cohérentes.
9. Redémarrer le Pi → revenir dans l'app → toutes les calibrations doivent être persistées (sublabels verts).
10. Power-cycle la monture → backlash + cordwrap doivent rester réglés (mémoire AUX monture).

---

# Risks / open questions

## Risque 1 : ADXL345 + LIS3MDL — séquence init register non validée hardware

Les valeurs de registres dans `lis3mdl_adapter.py` (CTRL_REG1..4) et `adxl345_adapter.py` (POWER_CTL, DATA_FORMAT, BW_RATE) sont issues de la datasheet **sans validation physique**. Premier smoke test capteur (à inclure dans Slice A Task A-2/A-3 review) :

```bash
# Sur le Pi
cd backend
ASTRO_BRAIN_HARDWARE=1 python -c "
from astro_brain.adapters.lis3mdl_adapter import Lis3mdlAdapter
import asyncio
async def t():
    a = Lis3mdlAdapter()
    await a.start()
    for _ in range(10):
        print(await a.read_raw())
        await asyncio.sleep(0.2)
asyncio.run(t())
"
```

Si valeurs aberrantes ou erreur I2C → ajuster registres avant de poursuivre Slice A. **Prendre 30 min pour ce smoke avant de lancer Task A-4 et suivantes.**

**Décision requise utilisateur :** OK pour intercaler ce smoke entre Task A-3 et Task A-4 ?

## Risque 2 : Algorithme ellipsoid fit (LIS3MDL)

Plusieurs approches possibles :
- **Li-Lawley** (analytique, SVD) — référence : Teslabs blog post.
- **Algorithme géométrique itératif** (Powell minimization).
- **Lib externe** (`pycal` ou `imucal`) — ajoute une dépendance.

Recommandation : Li-Lawley analytique, ~50 LOC, pas de dépendance externe. **Le reviewer "spec" de Task A-5 doit valider** que le pseudo-code utilisé matche la référence publique citée.

**Décision requise utilisateur :** OK pour Li-Lawley sans dep externe, ou préférence pour `imucal` (ajouterait une dep core) ?

## Risque 3 : Calibration session — race lors du disconnect SSE mid-sampling

**Décision retenue dans le plan :** la session reste active si le client SSE se disconnect. Implication : tout `start` ultérieur retourne 409 jusqu'à `abort` explicite ou TTL.

**Alternative non retenue :** auto-abort après N secondes sans subscriber SSE actif. Ajoute de la complexité (timer + tracking subscribers) pour un cas edge mineur.

**Décision requise utilisateur :** OK pour comportement simple "session reste active jusqu'à abort/finalize explicite" ? Ou ajout d'un TTL (ex. 60 s sans subscriber → auto-abort) ?

## Risque 4 : Heading tilt-compensé en v0.2 — RÉSOLU

**Décision arbitrée 2026-05-04 :** v0.2 livre tilt-compensé. La fusion utilise l'ADXL **monture** (pas tube) co-localisé avec le compass sur la base tournante, ce qui donne un vecteur gravité local au LIS3MDL. La mise en station impose de toute façon une monture nivelée, donc l'utilisateur fait l'item #1 avant utilisation.

Implémentation : Task A-5b (helper pure numpy `tilt_compensated_heading()` + `naive_heading()` fallback). Stream payload inclut `tilt_compensated: bool`. Si ADXL mount non calibré, fallback naïve + UI signale visuellement (Task A-12). Tests pure-numpy couvrent rotations pitch/roll de 5-10° sans hardware.

Pas un risque actif — listé pour la traçabilité.

## Risque 5 : Latence GET `/mount/tuning` — 4 reads INDI sequential

Spec promet ~50 ms par read AUX. 4 reads → 200 ms. UI fluide ? **À monitorer** au smoke Slice D. Optimisation possible : batch read en lisant la property entière `MOUNT_AXIS_BACKLASH` (4 valeurs en un seul roundtrip ; déjà comme ça côté driver). Vérifier que `getNumber("MOUNT_AXIS_BACKLASH")` retourne déjà les 4 elements en un appel — si oui, latence → 50 ms.

Pas de risque bloquant, juste un point de vigilance.

## Question ouverte 1 : Format hint calibration

Les hints (`"Maintenir immobile"`, `"Réduire les vibrations"`) sont en français. Le reste de l'app suit cette convention (cf. SetupCard sublabels). On garde français côté backend (les hints sont string brutes traversant l'API). Acté.

## Question ouverte 2 : Timing des merges

Recommandation : merger chaque slice dans `main` dès qu'elle est verte plutôt que d'attendre la fin du milestone. Bénéfices : réduit les conflits, permet de pousser/déployer Slice A sur le Pi sans attendre Slice D. Inconvénient : main porte un état partiel de v0.2 entre les merges (mais le scope est isolé par item, donc OK).

**Décision requise utilisateur :** OK pour merge incrémental par slice (plutôt qu'un mégamerge final) ?

---

## Récapitulatif des commits attendus

### Slice infra (~7 commits)
1. `chore(backend): add aiosqlite, numpy core + smbus2 hardware deps for v0.2 Setup`
2. `feat(backend): pydantic models for calibration payloads`
3. `feat(backend): aiosqlite repository scaffolding + initial migration`
4. `feat(backend): calibration_sensor repository (typed CRUD)`
5. `feat(backend): mount_limits repository (typed CRUD)`
6. `feat(backend): wire aiosqlite DB into FastAPI lifespan`
7. `deploy: add StateDirectory=astro-brain for sqlite state.db`
8. `docs: architecture + state-model — sqlite state.db + calibration off-bus`

### Slice A (~13 commits)
9. `feat(backend): i2c helpers (lazy smbus2 import + fake stub)`
10. `feat(backend): LIS3MDL I2C adapter (raw mag readings)`
11. `feat(backend): ADXL345 I2C adapter (mount + tube factories)`
12. `feat(backend): bias+sigma fit for ADXL345 calibration`
13. `feat(backend): ellipsoid fit (hard-iron + soft-iron) for LIS3MDL calibration`
14. `feat(backend): calibration service (state machine + sampling + persistence)`
15. `feat(backend): /calibration REST + SSE routes`
16. `feat(backend): /sensors/tilt + /sensors/compass SSE streams (lazy)`
17. `feat(app): calibration models + api service helpers`
18. `feat(app): tilt + compass SSE stream services`
19. `feat(app): item #1 niveau monture (ADXL345 mount calibration screen)`
20. `feat(app): item #2 compass (LIS3MDL calibration screen)`
21. `feat(app): item #3 zéro ALT (ADXL345 tube calibration screen)`

### Slice B (~2 commits)
22. `feat(backend): /limits/alt REST routes`
23. `feat(app): item #4 courses ALT min/max screen`

### Slice C (~2 commits)
24. `feat(backend): /about route (versions, network, uptime)`
25. `feat(app): item #9 about screen`

### Slice D (~3 commits + 1 smoke)
26. `feat(backend): /mount/tuning REST routes (passe-plat AUX)`
27. `feat(app): item #5 + #6 backlash ALT/AZ screens (parameterized)`
28. `feat(app): item #7 cordwrap screen`
29. `(smoke E2E commit + journal entry)`

### Final (~3 commits)
30. `docs(api): add v0.2 Setup endpoints`
31. `docs: add v0.2 Setup smoke checklist sections`
32. `docs(journal): v0.2 Setup livrée`

**Total estimé : ~32 commits, répartis sur 5 branches.**

---

## Critical Files for Implementation

- `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/services/calibration.py` (à créer — cœur du flow item #1/#2/#3)
- `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/repository/state_db.py` (à créer — pré-requis transversal)
- `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/adapters/mount_indi_adapter.py` (existe — backlash + cordwrap déjà prêts ; lecture seule ici)
- `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/backend/astro_brain/app.py` (modifié à chaque slice pour wire routers + adapters + DB)
- `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/app/lib/features/setup/setup_screen.dart` (modifié à chaque slice pour activer une carte)
