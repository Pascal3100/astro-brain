# Refacto archi — nettoyage & affinage backend/app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Appliquer les corrections actées dans la revue d'archi 2026-08 (code mort, commentaires trompeurs, correctness event-loop, sigma, position GPS hors bus, alignement INDI-source-de-vérité).

**Architecture:** Corrections isolées par tranche sur la branche `refacto/archi-review`. Contexte complet et rationale : [`docs/project/revue-archi-2026-08.md`](../../project/revue-archi-2026-08.md). Chaque tâche est une correction indépendante validée par la suite de tests.

**Tech Stack:** Backend FastAPI Python 3.13 (uv, pytest-asyncio `asyncio_mode=auto`) ; app Flutter (flutter_bloc, `flutter test`/`flutter analyze`).

## Global Constraints

- **Python** : respecter PEP 8 / 257 / 484 (`X | None`, pas `Optional`). `from __future__ import annotations` déjà en tête des modules.
- **Tests backend** : depuis `backend/`, `uv run pytest` (testpaths=`tests`). Migrations : forward-only, jamais d'édition d'une migration passée — toujours une nouvelle `_NNN_*.py` avec `VERSION`/`SQL`.
- **Tests app** : depuis `app/`, `flutter analyze` (zéro warning nouveau) + `flutter test`.
- **Aucun changement de comportement observable** hors items explicitement fonctionnels (B3 sigma, A2, A1). Les tranches 1/B4/B1 sont iso-comportement.
- **Pas de suppression sans preuve d'absence de référence** : `grep -rn <symbole>` sur `backend/astro_brain` + `backend/tests` (resp. `app/lib` + `app/test`) doit être vide hors définition avant suppression.
- **ADR** : les tâches A2 et A1 ajoutent une entrée datée dans `docs/project/decisions.md` (décision structurante).
- **Roadmap** : refacto transverse, pas d'étape du train → pas de mise à jour `roadmap.md`. Journal : une entrée de session au commit final.

---

### Task 1: Backend — code mort + commentaires (hors schéma)

**Files:**
- Delete symbol: `backend/astro_brain/services/_alignment_solver.py` (`_unit_vec_to_az_alt`, ~l.25-30)
- Delete symbol: `backend/astro_brain/adapters/_indi_property_helpers.py` (`set_number_values` ~l.43, `indi_state_string` ~l.70)
- Rename: `backend/astro_brain/services/_tilt_compensated_heading.py` → `backend/astro_brain/services/_heading.py` (+ tous les imports)
- Modify (comment): `backend/astro_brain/services/catalog/interpolation.py` (docstring/commentaire « partagé avec le resolver »)
- Modify (comment): `backend/astro_brain/routes/alignment.py:~222` (« 10° » → plancher réel 20°)
- Modify (doc): `docs/technical/api.md` (section `/reference/*`)
- Modify (doc): `docs/project/backlog.md`
- Test: suite existante

**Interfaces:**
- Consumes: rien (suppressions/renommages).
- Produces: `_heading.py` exporte la même fonction `naive_heading` qu'avant (signature inchangée).

- [ ] **Step 1: Prouver le code mort.** Pour chaque symbole (`_unit_vec_to_az_alt`, `set_number_values`, `indi_state_string`), `grep -rn '<symbole>' backend/astro_brain backend/tests`. Attendu : seule la définition (et son `__all__` éventuel) apparaît. Si un test le référence, STOP et remonter.
- [ ] **Step 2: Supprimer** les trois symboles morts + toute entrée `__all__`/import associée.
- [ ] **Step 3: Renommer** `_tilt_compensated_heading.py` → `_heading.py`. `grep -rn '_tilt_compensated_heading' backend` pour recâbler chaque import. Le module ne contient que `naive_heading` (docstring « no tilt compensation ») — ajuster le module docstring pour refléter « heading magnétique brut (pas de compensation d'inclinaison) ».
- [ ] **Step 4: Corriger les commentaires** : `interpolation.py` (retirer la fausse mention « partagé avec le resolver » — vérifier la réalité avant de reformuler) et `alignment.py` (aligner le commentaire sur le plancher effectif 20°, vérifié dans le code de la route).
- [ ] **Step 5: `api.md`** — documenter `GET /reference/status` + `POST /reference/sync` comme **endpoints ops/diagnostic** (re-sync manuel / health probe), sans consommateur app. Une phrase, au bon endroit de la doc des routes.
- [ ] **Step 6: `backlog.md`** — ajouter une entrée : « Garde version référence au moment du GoTo : si le Pi renvoie 404 sur un id que le téléphone connaît, surfacer "référence Pi périmée". Alternative légère à un écran de statut Pi (cf. revue archi A3). »
- [ ] **Step 7: Tests.** `cd backend && uv run pytest`. Attendu : PASS (aucun test ne dépendait du code mort).
- [ ] **Step 8: Commit** `refactor(backend): remove dead helpers, rename heading module, fix stale comments`.

---

### Task 2: Backend — migration DROP `mount_limits`

**Files:**
- Create: `backend/astro_brain/repository/migrations/_005_drop_mount_limits.py`
- Test: `backend/tests/` (test de migration existant — localiser via `grep -rn 'run_migrations\|_discover_migrations' backend/tests`)

**Interfaces:**
- Consumes: mécanisme `run_migrations` (state_db.py) — découvre les modules `_NNN_*` par `VERSION`/`SQL`, applique en ordre lexical. Tête actuelle = `_004` (VERSION 4).
- Produces: schéma à VERSION 5 sans table `mount_limits`.

- [ ] **Step 1: Prouver l'absence d'usage.** `grep -rn 'mount_limits' backend/astro_brain backend/tests`. Attendu : uniquement la création dans `_001_initial.py`. Sinon STOP.
- [ ] **Step 2: Écrire la migration** (miroir exact de `_004_drop_catalog_objects.py`) :

```python
"""Retire la table `mount_limits`.

Résidu Courses ALT / limites monture jamais lues ni écrites (cf. revue
archi 2026-08). Forward-only.
"""
from __future__ import annotations

VERSION = 5

SQL = """
DROP TABLE IF EXISTS mount_limits;
"""
```

- [ ] **Step 3: Test migration.** Vérifier via le test de migration existant que le schéma monte jusqu'à VERSION 5 sur une base neuve ET sur une base déjà à VERSION 4 (idempotence forward-only). Ajouter une assertion `sqlite_master` ne contient plus `mount_limits` si le pattern des tests le permet.
- [ ] **Step 4: Tests.** `cd backend && uv run pytest`. Attendu : PASS.
- [ ] **Step 5: Commit** `refactor(backend): drop dead mount_limits table (migration _005)`.

---

### Task 3: App — code mort + commentaires

**Files:**
- Modify: `app/lib/models/calibration.dart` (classe `Adxl345Offsets` ~l.46-73 + branche `fromJson` inatteignable ~l.221)
- Modify: `app/lib/theme/theme_cubit.dart` (`setDay()`/`setNight()` ~l.40-48)
- Modify: `app/lib/models/about.dart` (`appVersionSeen` ~l.31,50,61)
- Modify: `app/lib/features/setup/reference/reference_models.dart` (DTO `ReferenceStatusDto.fromJson`/`ReferenceSyncResultDto.fromJson` + commentaire « miroir des routes »)
- Modify: `app/lib/features/catalogue/catalogue_models.dart` (`CatalogObjectDto.fromJson` ~l.58 — **conditionnel**)
- Modify (comments): `app/lib/features/catalogue/local/visibility.dart:2`, `local_catalogue.dart:2`, `catalogue_providers.dart:2`, `catalogue_screen.dart:~364-365`

**Interfaces:**
- Consumes: rien.
- Produces: modèles allégés ; aucun champ consommé par un widget ne disparaît (vérifier avant suppression).

- [ ] **Step 1: Prouver le code mort.** Pour chaque symbole (`Adxl345Offsets`, `setDay`, `setNight`, `appVersionSeen`, `ReferenceStatusDto`, `ReferenceSyncResultDto`, `CatalogObjectDto.fromJson`), `grep -rn '<symbole>' app/lib app/test`. Attendu hors définition : vide. **Exception `CatalogObjectDto.fromJson`** : s'il est référencé par un test, le **garder** et ne rien changer sur lui.
- [ ] **Step 2: Supprimer** `Adxl345Offsets` + rendre la logique `fromJson` du modèle calibration mono-branche (la branche `else → Adxl345Offsets` devient morte → retirer). Vérifier qu'aucun `is Adxl345Offsets` ne subsiste.
- [ ] **Step 3: Supprimer** `ThemeCubit.setDay()`/`setNight()` (le toggle passe par une autre API — le confirmer par grep).
- [ ] **Step 4: Supprimer** le parse `appVersionSeen` de `about.dart` (jamais affiché — confirmer aucun widget ne le lit).
- [ ] **Step 5: Supprimer** les DTO morts `ReferenceStatusDto.fromJson`/`ReferenceSyncResultDto.fromJson` et corriger le commentaire de tête `reference_models.dart` : ces modèles décrivent la copie **locale** (téléphone), **pas** un miroir des routes `/reference/*` du Pi.
- [ ] **Step 6: Corriger les commentaires** : `visibility.dart` (ne cite plus `backend/.../catalog/visibility.py` inexistant — décrire la vraie source) ; `local_catalogue.dart`/`catalogue_providers.dart` (« port de … » → « logique app ; le backend ne résout que par id ») ; `catalogue_screen.dart` `_KindDropdown` (filtrage **local**, pas backend).
- [ ] **Step 7: Vérif.** `cd app && flutter analyze` (pas de nouveau warning) + `flutter test`. Attendu : PASS.
- [ ] **Step 8: Commit** `refactor(app): remove dead models/methods, fix misleading comments`.

---

### Task 4: Backend — I2C LIS3MDL non-bloquante (B2)

**Files:**
- Modify: `backend/astro_brain/adapters/lis3mdl_adapter.py` (`start`, `stop`, `read_raw`)
- Test: `backend/tests/` (test adapter compass existant / fake I2C)

**Interfaces:**
- Consumes: `_i2c_helpers` (`write_byte`, `read_bytes` — synchrones).
- Produces: mêmes signatures `async def`, mais les appels I2C bloquants passent par `asyncio.to_thread` (cf. `mount_indi_adapter.py`, 18 usages).

- [ ] **Step 1: Test.** Écrire/étendre un test qui vérifie que `read_raw`/`start`/`stop` délèguent les I/O bloquantes hors de l'event loop. Si un fake I2C existe, asserter que l'appel est bien awaité via `to_thread` (p.ex. patcher `asyncio.to_thread` et vérifier l'appel, ou vérifier qu'un `write_byte` lent ne bloque pas une tâche concurrente). Choisir la forme la plus proche du style de test existant.
- [ ] **Step 2: Run** le test → FAIL (appel synchrone actuel).
- [ ] **Step 3: Wrapper** chaque I/O synchrone (`write_byte`, `read_bytes`) dans `await asyncio.to_thread(...)` dans `start`/`stop`/`read_raw`. Ne pas changer les signatures publiques.
- [ ] **Step 4: Run** → PASS. Puis `uv run pytest` complet.
- [ ] **Step 5: Commit** `fix(backend): run LIS3MDL I2C off the event loop (to_thread)`.

---

### Task 5: Backend — helper d'erreur mount adapter (B4)

**Files:**
- Modify: `backend/astro_brain/adapters/mount_indi_adapter.py` (blocs `except` répétés ~l.360,411,456,475,505,532,613,648,679,723)
- Test: suite adapter existante (comportement inchangé)

**Interfaces:**
- Consumes: `self._bus.publish("mount", SubsystemState(...))`, `logger`.
- Produces: méthodes privées `_publish_error(self, exc: Exception) -> None` et/ou `_publish_mount(self, state: str, **details) -> None` ; comportement (log + publish) **identique**.

- [ ] **Step 1: Cartographier** les ~10 blocs `except Exception as exc: logger.exception(...); self._bus.publish("mount", SubsystemState(state="error", ...))`. Noter les variantes (message de log, details publiés) — le helper doit les préserver ou les paramétrer.
- [ ] **Step 2: Extraire** `_publish_error(exc, *, context: str)` (log `exception` + publish `state="error"`) et, si utile, `_publish_mount(state, **details)`. Remplacer chaque bloc par un appel. Aucune modification du message/details observable.
- [ ] **Step 3: Tests.** `uv run pytest` (les tests adapter existants couvrent les chemins d'erreur). Attendu : PASS sans modification de test. Si un test asserte un message précis, le préserver via le paramètre `context`.
- [ ] **Step 4: Commit** `refactor(backend): extract mount adapter error-publish helper`.

---

### Task 6: Backend — helper d'itération bus partagé (B1, DOWNGRADÉ)

> **⚠️ Décision à confirmer avant dispatch** (voir handoff). La revue actait « 3 réacteurs → 1 dispatcher ». La lecture du code montre que les 3 réacteurs ont des **responsabilités distinctes** (orchestrator = mount+gps edge-trigger ; supervisor = boucle de reconnexion backoff longue ; invalidator = invalidation edge-trigger) : les fusionner en une classe **conflaterait 3 responsabilités** et forcerait la boucle backoff bloquante dans un dispatch partagé (régression). Le seul vrai doublon est le prologue `async for _event in bus.subscribe(): full = bus.get_full_state()`. → **On extrait un petit itérateur partagé, on garde les 3 réacteurs séparés.**

**Files:**
- Modify: `backend/astro_brain/bus.py` (ou un nouveau `backend/astro_brain/_bus_events.py`) — ajouter l'itérateur
- Modify: `backend/astro_brain/orchestrator.py`, `mount_connection_supervisor.py`, `alignment_invalidator.py`
- Test: tests réacteurs existants

**Interfaces:**
- Produces: `async def iter_state_snapshots(bus: StateBus) -> AsyncIterator[dict[str, SubsystemState]]` — yield `bus.get_full_state().subsystems` à chaque event du bus.
- Consumes (réacteurs) : remplacent leur prologue par `async for subsystems in iter_state_snapshots(self._bus): ...`.

- [ ] **Step 1: Test.** Test unitaire de `iter_state_snapshots` : sur un bus fake qui publie N events, l'itérateur yield N snapshots `subsystems`.
- [ ] **Step 2: Run** → FAIL (n'existe pas).
- [ ] **Step 3: Implémenter** l'itérateur puis réécrire les 3 `run()` pour le consommer. Logique de réaction (`_maybe_sync`, `_recover`, `on_mount_state`) **inchangée**.
- [ ] **Step 4: Run** → PASS + `uv run pytest` complet (les 3 réacteurs gardent leurs tests).
- [ ] **Step 5: Commit** `refactor(backend): share bus-snapshot iterator across mount reactors`.

---

### Task 7: Backend — sigma de calibration calculé (B3)

**Files:**
- Modify: `backend/astro_brain/services/_ellipsoid_fit.py` (résidu RMS après fit)
- Modify: `backend/astro_brain/services/calibration.py` (`_sigma` ~l.70,104,154,161 — plus de `0.0` figé)
- Verify: `app/lib/features/setup/calibration/calibration_progress.dart:~78` (affichage `SIGMA` — déjà câblé)
- Test: `backend/tests/` (test ellipsoid_fit / calibration)

**Interfaces:**
- Produces: le fit retourne un `sigma` (RMS des résidus = écart des échantillons corrigés à la sphère unité) ; `calibration.py` le propage au lieu de `0.0`.

- [ ] **Step 1: Test.** Pour un jeu d'échantillons synthétiques **bruités** (donc fit imparfait), asserter `sigma > 0`. Pour des échantillons parfaits sur une sphère, `sigma ≈ 0` (tolérance). Localiser le test de fit existant pour le style.
- [ ] **Step 2: Run** → FAIL (sigma actuellement 0.0).
- [ ] **Step 3: Implémenter** dans `_ellipsoid_fit.py` : après estimation (hard/soft-iron), corriger chaque échantillon, calculer `residual_i = norm(corrected_i) - 1`, `sigma = sqrt(mean(residual_i**2))`. Le retourner et le propager dans `calibration.py` (init, reset, passes live + finale) à la place du `0.0`.
- [ ] **Step 4: Run** → PASS + `uv run pytest`.
- [ ] **Step 5: Vérif app.** Confirmer que `calibration_progress.dart` affiche désormais un sigma non nul (lecture code ; pas de device requis). Pas de changement app nécessaire si le wire existe déjà.
- [ ] **Step 6: Commit** `feat(backend): compute calibration fit residual (sigma)`.

---

### Task 8: Backend — position GPS hors bus santé (A2)

**Files:**
- Modify/Create: source typée de position GPS (accesseur dédié, p.ex. sur le service/adapter GPS) au lieu de `bus.get_full_state().subsystems["gps"].details["lat"/"lon"]`
- Modify: `backend/astro_brain/app.py:~96-105` (`_AlignmentSensorsBridge.gps_fix`)
- Modify: `backend/astro_brain/orchestrator.py:~57-58` (sync heure/lieu)
- Modify: `docs/project/decisions.md` (ADR daté)
- Test: tests orchestrator + bridge

**Interfaces:**
- Produces: un accesseur typé `GpsFix | None` (lat/lon/timestamp) exposé par la couche GPS, indépendant du dict `details` du bus santé.
- Consumes: orchestrator + bridge lisent cet accesseur ; le bus santé ne transporte plus la position comme donnée fonctionnelle.

- [ ] **Step 1: Concevoir** l'accesseur : où vit la vérité GPS live (l'adapter/service GPS qui publie déjà l'état santé) ? Exposer un `latest_fix() -> GpsFix | None` typé (dataclass `GpsFix(lat, lon, ...)`), alimenté par la même source que la pastille santé mais **distinct** du `details` dict.
- [ ] **Step 2: Test.** Adapter les tests orchestrator/bridge pour injecter la position via le nouvel accesseur (fake). Asserter que le sync monture reçoit lat/lon depuis l'accesseur, pas depuis `details`.
- [ ] **Step 3: Run** → FAIL, puis implémenter, → PASS.
- [ ] **Step 4: Recâbler** `orchestrator._maybe_sync` et `_AlignmentSensorsBridge.gps_fix` pour lire l'accesseur. Le bus santé garde la pastille GPS mais n'est plus la voie de la donnée fonctionnelle.
- [ ] **Step 5: ADR.** Entrée datée dans `decisions.md` : « Position GPS live via source typée, hors bus santé (fin conflation bus/live) ».
- [ ] **Step 6: Tests** complets + **Commit** `refactor(backend): expose GPS fix via typed source, off the health bus`.

---

### Task 9: Backend — alignement : INDI source de vérité (A1) — **BLOQUÉ sur vérif Pi**

> Ne démarre qu'après une vérification sur le Pi (le driver `indi_celestron_aux` expose-t-il le nombre de points de sync / la présence du modèle en Property lisible ?). Voir handoff. `AlignmentInvalidator` gère déjà la perte du modèle à la reconnexion ; il ne manque que la **dérivation de `is_aligned` au boot** quand indiserver a survécu au restart backend.

**Files:**
- Modify: `backend/astro_brain/services/alignment.py` (`is_aligned` dérivé de l'état mount/INDI, pas bool RAM initialisé à False)
- Modify: `backend/astro_brain/services/_alignment_solver.py` (retirer le calcul + `svd_matrix` si branche « INDI expose l'état »)
- Modify: `backend/astro_brain/repository/alignment_repo.py` + migration (retirer/alléger la persistance selon la branche retenue)
- Modify: `backend/astro_brain/app.py:~255` (câblage load selon branche)
- Modify: `docs/project/decisions.md` (ADR : fin du double modèle de pointage)
- Test: tests alignment + repo

**Interfaces:**
- **Branche A (INDI expose l'état)** : `is_aligned` lu depuis l'état mount/INDI au boot + reconnexion ; suppression complète du `svd_matrix` persisté et de `alignment_repo.load()`. Zéro persistance d'alignement.
- **Branche B (INDI n'expose pas)** : persistance minimale des 3 points (star + timestamp) ; `load()` (freshness 12h/GPS-delta) rejoue `sync_radec` à la reconnexion pour reconstruire le modèle natif. `svd_matrix` supprimé dans les deux cas.

- [ ] **Step 0 (prérequis, hors subagent) : vérif Pi.** Lire les Properties du device via le client INDI (nombre de points de sync / présence modèle). Consigner le résultat → choisit la branche.
- [ ] **Step 1: Test** de la dérivation `is_aligned` selon la branche (fake mount exposant / n'exposant pas le modèle).
- [ ] **Step 2..N** : implémenter la branche retenue ; supprimer `svd_matrix` + `_unit_vec_to_az_alt` déjà retiré en Task 1 ; nettoyer `_alignment_solver`/`alignment_repo`/migration en conséquence.
- [ ] **ADR** daté + **Commit** `refactor(backend): derive alignment from INDI, drop dead SVD model`.

---

## Appendix — Tranche 6 (E, micro-optims) : à la carte, hors exécution automatique

Non planifiées en tâches — à piocher à la demande : `overall` recalculé ~4×/publish (`bus.py`) · `coverage_pct` reboucle une constante 4³ (`_ellipsoid_fit.py:149-168`) · `GlobalDot` anime hors pulse · `SystemScreen` sans `buildWhen` · helper `SseConnection` partagé (3 services) · setup souscription dupliqué `app_bloc.dart:26-32` vs `49-55`.

## Self-Review

- **Couverture revue** : tranches 1-5 du doc de revue → Tasks 1-9. Tranche 6 (E) explicitement à la carte. ✅
- **Placeholders** : aucun « TBD » ; les refactors donnent la règle de transformation + interfaces + test. A1 a une branche conditionnelle explicite (dépendance Pi documentée). ✅
- **Cohérence des noms** : `iter_state_snapshots`, `_publish_error`/`_publish_mount`, `GpsFix.latest_fix`, `sigma` — utilisés de façon cohérente. ✅
- **Ordre** : suppressions (1-3) avant refactors (4-9) ; A1 en dernier car bloqué Pi et dépend du nettoyage Task 1. ✅
