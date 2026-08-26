# Retrait du module DroTek (GPS Ublox M8N + compass LIS3MDL) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retirer intégralement le module DroTek — GPS Ublox M8N (UART0 + gpsd) **et** compass LIS3MDL `0x1E` (I2C1) — du backend, de l'app Flutter, des docs vivantes et du Pi ; et remplacer ce qu'il portait réellement par un **site d'observation persisté** (lat/lon en base, alimenté par le GPS du téléphone) plus une **garde d'horloge** avant la sync heure vers la monture. Cf. ADR [2026-08-26 « Retrait du module DroTek »](../../project/decisions.md).

**Architecture :** Le module ne portait que deux fonctions vivantes : (1) une **position** consommée par le wizard d'alignement (`_AlignmentSensorsBridge.position()`), (2) un **déclencheur de sync** vers la monture (`Orchestrator`, qui poussait `datetime.now(UTC)` — l'heure NTP du Pi, jamais celle du GPS). Le compass, lui, n'alimentait qu'un affichage (`GET /sensors/compass/stream`) : **aucun** chemin alignement / goto / slew ne lit un cap.

La bascule se fait donc en **additif d'abord, soustractif ensuite** :

1. on pose le **site d'observation** (table `observing_site`, `GET`/`PUT /site`, chargé en mémoire au boot) et on le branche en dernier recours de la chaîne de position ;
2. on rend l'`Orchestrator` indépendant du GPS (déclencheur = monture `ready`) et on garde la poussée d'heure derrière un test de synchro NTP ;
3. on supprime le GPS (adapter gpsd, protocoles, sous-système `gps` du bus et de l'app) ;
4. on supprime le compass et **toute la chaîne de calibration** qui n'existait que pour lui (service, repo, routes, modèles, fit d'ellipsoïde, heading, écrans Flutter) ;
5. on met les docs vivantes et le Pi au même niveau.

**Tech Stack :** Backend FastAPI / Python 3.13 (uv, pytest, aiosqlite/SQLite). App Flutter (`flutter_bloc`, `mocktail`, `geolocator` déjà présent). Docs Markdown + schémas HTML/SVG statiques. Ops Pi OS 64-bit Lite (systemd, apt).

## Décisions actées (baked-in, ne pas re-débattre en exécution)

Issues de la discussion ayant produit ce plan et de l'ADR 2026-08-26 :

1. **Le module part en entier**, pas seulement le compass. Le compass est physiquement absent du bus I2C depuis au moins S50 et aucune calibration n'a été persistée depuis S42 : le système a tourné des semaines sans, sans dégradation mesurable. Ce n'est pas un pari, c'est une mesure.
2. **La chaîne de position devient : site d'observation persisté → sinon rien** (409 côté wizard). Le « fallback GPS téléphone » ne disparaît pas — il devient le **moyen d'écrire le site**, pas une source parallèle. Un seul concept, une seule source de vérité.
3. **Le site ne s'écrit que sur action explicite** de l'utilisateur (carte Setup, ou le rattrapage 409 du wizard). Jamais automatiquement au lancement de l'app : la garde ΔGPS 20 m d'`alignment_repo.load` comparerait alors le modèle persisté à un GPS téléphone qui gigue de ~10 m et invaliderait l'alignement sans raison.
4. **Les colonnes `gps_lat` / `gps_lon` du modèle d'alignement ne sont pas renommées.** Schéma appliqué = immuable ; seule leur *sémantique* change (position du site au moment du `record`). Un commentaire le dit dans `models/alignment.py`.
5. **L'heure reste NTP**, elle n'a jamais été GPS (`orchestrator` pousse `datetime.now(UTC)`, aucun `chrony`/`gpsd` n'a jamais discipliné l'horloge). On ajoute seulement la garde qui manquait : sans synchro réseau, `fake-hwclock` restitue l'heure du dernier arrêt et on la poussait dans la monture **sans aucun contrôle**. C'est un défaut latent corrigé ici, pas une régression du retrait.
6. **Pas de nouveau `SubsystemKind`** pour l'horloge : l'info sort dans `details` du sous-système `system` existant (`clock_synced`). Un sous-système de plus pour un booléen serait de la sur-promotion.
7. **`enable_uart=1`, `dtoverlay=disable-bt` et le `serial-getty@ttyAMA0` désactivé RESTENT.** Ils sont recyclés tels quels par le pont ESP32 filaire (plan [2026-08-26-pont-esp32-serie.md](2026-08-26-pont-esp32-serie.md), à exécuter **après** celui-ci). Les toucher casserait la tâche suivante.
8. **Le pré-pointage automatique des étoiles #2/#3 n'est PAS dans ce périmètre.** C'est du travail de feature Macro 3, additif, avec une vraie question de sécurité (un goto sur modèle 1 point peut envoyer le tube dans la fourche ou le trépied, et l'anti-collision ALT n'a jamais été reprise depuis l'ADR 2026-07-17). Il a sa propre entrée backlog et sa propre ligne roadmap.

## Global Constraints

- **PEP 8 / 257 / 484-604** sur tout le Python touché (typage moderne `X | None`). Docstrings à jour, pas de référence morte.
- **Ne pas éditer les docs historiques** : `docs/superpowers/specs/*`, `docs/superpowers/plans/*` (sauf ce fichier), `docs/project/journal/archive/*`. Enregistrements figés.
- **Migrations SQLite appliquées = immuables.** On n'édite jamais `_001`…`_006` ; on ajoute `_007` (création) et `_008` (drop). Sauvegarder `state.db` sur le Pi avant le pull qui les apporte.
- **`SensorUnavailableError` et `ConflictError` RESTENT** dans `services/interfaces.py` : la monture (`current_position`) et le wizard d'alignement les utilisent. Seuls leurs usages compass/calibration disparaissent.
- **Ne pas toucher au chemin monture** (`mount_indi_adapter`, `MountConnectionSupervisor`, routes `commands`/`goto`) hors des points explicitement listés (orchestrateur, `_serial_device`).
- **Chaque tâche finit verte** : `uv run pytest` (backend) / `flutter analyze && flutter test` (app), plus un grep de non-régression prouvant que les symboles retirés ont disparu.
- Commandes backend depuis `backend/` ; commandes Flutter depuis `app/`.
- Commits atomiques par tâche, en français, style du repo (`feat(...)`, `refactor(...)`, `docs(...)`).
- Ordre des tâches **non permutable** : 1 (additif) → 2 → 3 → 4 → 5 → 6 → 7.

---

## Task 1 : Backend — poser le site d'observation persisté

**Files:**
- Create: `backend/astro_brain/repository/migrations/_007_observing_site.py`
- Create: `backend/astro_brain/repository/site_repo.py`
- Create: `backend/astro_brain/routes/site.py`
- Create: `backend/tests/test_site_repo.py`
- Create: `backend/tests/test_site_routes.py`
- Modify: `backend/astro_brain/app.py` (`_AlignmentSensorsBridge`, lifespan, `include_router`)
- Modify: `backend/astro_brain/models/alignment.py` (commentaire de sémantique sur `gps_lat`/`gps_lon`)
- Modify: `backend/tests/test_state_db.py` (version 6 → 7, table `observing_site` présente)
- Modify: `backend/tests/test_alignment_sensors_bridge.py` (nouvelle chaîne de position)

**Interfaces:**
- Consumes: `aiosqlite.Connection` (`app.state.db`).
- Produces: `GET /site` → `{lat, lon, set_at} | null` ; `PUT /site {lat, lon}` → 204. `app.state.position_provider.position()` renvoie désormais aussi le site.

- [ ] **Étape 1 : Migration `_007_observing_site.py`**

Sur le modèle de `_005_drop_mount_limits.py` (module avec `VERSION` + `SQL`, forward-only, docstring qui dit *pourquoi*) :

```python
VERSION = 7

SQL = """
CREATE TABLE IF NOT EXISTS observing_site (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  set_at TEXT NOT NULL
);
"""
```

Le `CHECK (id = 1)` matérialise le singleton dans le schéma plutôt que dans le code appelant.

- [ ] **Étape 2 : `repository/site_repo.py`**

Deux fonctions typées, dans le style de `calibration_repo` (validation avant SQL, pas de `Any`) :

- `async def get_site(db) -> ObservingSite | None`
- `async def set_site(db, lat: float, lon: float) -> ObservingSite` — `INSERT INTO observing_site (id, lat, lon, set_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET ...`, `set_at` en ISO UTC.

`ObservingSite` : modèle Pydantic (`lat: float = Field(ge=-90, le=90)`, `lon: float = Field(ge=-180, le=180)`, `set_at: datetime`) posé dans le même module — il n'y a pas d'autre consommateur qui justifierait un fichier `models/site.py`.

- [ ] **Étape 3 : `routes/site.py`**

`GET /site` → `ObservingSite | None` (200 avec `null` quand aucun site : l'absence est un état nominal, pas un 404). `PUT /site` avec un body `{lat, lon}` → persiste **et** met à jour le provider en mémoire via `deps.get_position_provider`, puis `204`. Validation des bornes par Pydantic (422 automatique).

- [ ] **Étape 4 : Câbler le site dans `_AlignmentSensorsBridge` (`app.py`)**

Dans `_AlignmentSensorsBridge` (~L94-137) :
- renommer le champ `_client` en `_site` et `set_client_location` / `clear_client_location` en `set_site` / `clear_site` (la notion « client » disparaît — c'est le site) ;
- `position()` devient `return self.gps_fix() or self._site` **pour l'instant** (le GPS part en Task 3) ;
- mettre à jour la docstring de classe : « Chaîne de position : fix GPS Pi → site d'observation persisté → None ».

Dans le lifespan, **après** `run_migrations` et **avant** la construction d'`AlignmentServiceImpl` : charger le site (`await site_repo.get_site(db_conn)`) et le semer dans le bridge s'il existe.

`routes/alignment.py` : `POST /align/location/client` appelle désormais `position.set_site(...)` **et** persiste (`site_repo.set_site`). On garde la route à l'identique côté contrat — l'app Flutter bascule sur `PUT /site` en Task 5, et la route disparaît là.

- [ ] **Étape 5 : Commentaire de sémantique sur le modèle d'alignement**

Dans `astro_brain/models/alignment.py` (~L52-53), au-dessus de `gps_lat`/`gps_lon` : noter que les noms sont historiques (schéma appliqué, non renommé) et que la valeur est **la position du site d'observation** au moment du `record`, plus un fix GPS embarqué. Aucun changement de code.

- [ ] **Étape 6 : Tests**

`tests/test_site_repo.py` : absence → `None` ; écriture → relecture ; ré-écriture → une seule ligne (`SELECT COUNT(*)` = 1) et `set_at` mis à jour.
`tests/test_site_routes.py` : `GET` vide → `null` ; `PUT` valide → 204 puis `GET` renvoie la valeur ; `PUT` lat=91 → 422 ; `PUT` met bien à jour `position_provider.position()`.
`tests/test_state_db.py` : `version == 7` (2 occurrences) et `"observing_site"` dans l'ensemble des tables attendues.
`tests/test_alignment_sensors_bridge.py` : le cas « pas de fix GPS mais site connu » renvoie le site.

- [ ] **Étape 7 : Suite verte + commit**

Run: `uv run pytest -q`
Expected: PASS.
Run: `uv run python -c "import sqlite3,tempfile,asyncio"` *(sanity import, sans effet)* puis vérifier à la main : `grep -n "VERSION" astro_brain/repository/migrations/_007_observing_site.py`
Expected: `VERSION = 7`.

```bash
git add -A
git commit -m "feat(backend): site d'observation persisté (table + /site) en amont du retrait DroTek"
```

---

## Task 2 : Backend — orchestrateur sans GPS + garde d'horloge

**Files:**
- Create: `backend/astro_brain/adapters/clock_sync.py`
- Modify: `backend/astro_brain/orchestrator.py`
- Modify: `backend/astro_brain/adapters/system_info.py` (détail `clock_synced`)
- Modify: `backend/astro_brain/app.py` (construction de l'`Orchestrator`)
- Modify: `backend/tests/test_orchestrator.py`
- Modify: `backend/tests/test_system_info_adapter.py`

**Interfaces:**
- Consumes: bus (`mount`), `position_provider.position()`, `clock_sync.is_clock_synced()`.
- Produces: `set_location` sur site connu, `set_time` seulement si l'horloge est fiable ; `system.details.clock_synced`.

- [ ] **Étape 0 : Déterminer le démon de temps du Pi (pré-requis, à faire AVANT d'écrire l'adapter)**

Run (sur le Pi) : `timedatectl status; systemctl is-active systemd-timesyncd chrony 2>/dev/null; ls -l /run/systemd/timesync/synchronized`
Expected: identifier lequel tourne. Si `systemd-timesyncd` → la sonde est l'**existence du fichier** `/run/systemd/timesync/synchronized` (aucun sous-processus, appelable à chaque tick). Si `chrony` → replier sur `timedatectl show --property=NTPSynchronized --value` exécuté **dans un thread** (`asyncio.to_thread`) et espacé (une fois par minute, pas à chaque tick de 5 s). Noter le choix retenu dans la docstring du module.

- [ ] **Étape 1 : `adapters/clock_sync.py`**

Une fonction pure et bon marché : `def is_clock_synced() -> bool`, implémentée selon l'étape 0, sans exception qui remonte (tout échec de lecture ⇒ `False` : on refuse de pousser une heure qu'on ne sait pas valider). Docstring : expliquer le défaut qu'elle couvre (`fake-hwclock` restitue l'heure du dernier arrêt, hors réseau).

- [ ] **Étape 2 : Réécrire `Orchestrator`**

- Signature : `__init__(self, *, bus, mount, position, clock_synced: Callable[[], bool] = is_clock_synced)`. Plus de `gps`.
- Supprimer `GPS_FIX_STATES` et l'import de `GpsState`.
- `_maybe_sync` : la condition devient `mount_s.state == MountState.READY.value` seul. Rearmement inchangé sur la perte de la condition.
- Corps : `pos = self._position.position()`. Si `pos is not None` → `set_location(lat, lon)`. Si `self._clock_synced()` → `set_time(now_iso)`, sinon `logger.warning("orchestrator: horloge non synchronisée — heure NON poussée vers la monture")` et on ne pousse pas.
- `self._synced = True` seulement si **au moins une** des deux poussées a eu lieu — sinon on reste armé pour retenter au prochain événement de bus (l'horloge peut se synchroniser après le boot).
- Mettre à jour le docstring de module en tête de fichier (il décrit encore le couple mount+gps).

- [ ] **Étape 3 : `clock_synced` dans les détails `system`**

`SystemInfoAdapter` publie déjà des `details` à chaque tick : y ajouter `clock_synced: bool`. Ne pas toucher à `compute_state` — une horloge non synchronisée ne fait pas passer le Pi en `warning` (c'est légitime hors réseau, cf. ADR).

- [ ] **Étape 4 : Câblage `app.py`**

`Orchestrator(bus=bus, mount=services["mount"], position=sensors_bridge)`. ⚠️ `sensors_bridge` est construit **dans** le lifespan alors que l'orchestrateur l'est aujourd'hui **avant** (~L225) : déplacer la construction de l'`Orchestrator` dans le lifespan, juste avant `asyncio.create_task(orchestrator.run())`, et adapter la fermeture (`background_tasks`).

- [ ] **Étape 5 : Tests**

`tests/test_orchestrator.py` : réécrire autour du nouveau contrat — sync sur `mount ready` seul ; pas de `set_location` sans site ; pas de `set_time` avec `clock_synced=False` ; rearmement quand la monture décroche ; **et** le cas « horloge fausse au 1er événement, synchronisée au 2e » qui doit finir par pousser l'heure.
`tests/test_system_info_adapter.py` : `clock_synced` présent dans les détails publiés.

- [ ] **Étape 6 : Suite verte + non-régression + commit**

Run: `uv run pytest -q`
Expected: PASS.
Run: `grep -rn "GPS_FIX_STATES" astro_brain tests`
Expected: **aucun hit**.

```bash
git add -A
git commit -m "fix(backend): ne plus pousser l'heure vers la monture sans synchro NTP ; orchestrateur sans GPS"
```

---

## Task 3 : Backend — retirer le GPS

**Files:**
- Delete: `backend/astro_brain/adapters/gpsd_adapter.py`
- Delete: `backend/tests/test_gpsd_adapter.py`
- Delete: `backend/tests/test_gpsd_loop.py`
- Delete: `backend/tests/test_alignment_rehydrate_trigger.py` *(à réécrire — voir étape 5)*
- Modify: `backend/astro_brain/services/interfaces.py` (retirer `GpsFix`, `GpsSource`, `GpsService`)
- Modify: `backend/astro_brain/subsystems.py` (retirer `GpsState`)
- Modify: `backend/astro_brain/aggregator.py` (retirer les états GPS des sets)
- Modify: `backend/astro_brain/services/fakes.py` (retirer `FakeGps`)
- Modify: `backend/astro_brain/deps.py` (retirer `get_gps`)
- Modify: `backend/astro_brain/app.py` (`_select_services`, wiring, `_rehydrate_alignment_once`, `_AlignmentSensorsBridge.gps_fix`)
- Modify: `backend/astro_brain/services/alignment.py` (`gps_fix()` → `position()`)
- Modify: `backend/tests/test_app.py`, `test_state_endpoint.py`, `test_subsystems.py`, `test_aggregator.py`, `test_fakes.py`, `test_alignment_sensors_bridge.py`, `test_alignment_service.py`

**Interfaces:**
- Consumes: plus rien du GPS.
- Produces: `/state` n'expose plus de sous-système `gps` ; l'alignement lit la position du site.

- [ ] **Étape 1 : Confirmer l'inventaire avant de couper**

Run: `grep -rn "GpsSource\|GpsService\|GpsFix\|GpsState\|FakeGps\|GpsdAdapter\|latest_fix\|gps_fix" astro_brain tests --include=*.py`
Expected: hits uniquement dans les fichiers listés ci-dessus. Tout autre fichier = périmètre à élargir, à signaler.

- [ ] **Étape 2 : Supprimer les fichiers propres au GPS**

```bash
git rm astro_brain/adapters/gpsd_adapter.py \
       tests/test_gpsd_adapter.py \
       tests/test_gpsd_loop.py
```

- [ ] **Étape 3 : Élaguer les modules partagés**

- `services/interfaces.py` : supprimer `GpsFix`, `GpsSource`, `GpsService` (et l'import `datetime` s'il devient inutilisé). **Garder** `SensorUnavailableError`, `ConflictError`, tous les autres protocoles.
- `subsystems.py` : supprimer `GpsState`.
- `aggregator.py` : retirer `GpsState` de l'import, `GpsState.SEARCHING` de `TRANSIENT_STATES`, `GpsState.NO_FIX`/`OFF` de `DEGRADED_STATES`. `TRANSIENT_STATES` se réduit à `MountState.CONNECTING` — c'est correct, pas un oubli.
- `services/fakes.py` : supprimer `FakeGps` et l'import `GpsFix`.
- `deps.py` : supprimer `get_gps` et `GpsService` de l'import.

- [ ] **Étape 4 : `app.py`**

- `_select_services` : retirer les entrées `"gps"` (branche hardware **et** branche fakes) et l'import `GpsdAdapter` ; mettre à jour la docstring (« les cinq services »).
- Lifespan : retirer `await services["gps"].start()` et `.stop()`.
- `app.state.gps` : retirer.
- `_AlignmentSensorsBridge` : supprimer `gps_fix()`, l'argument `gps` du constructeur et le champ `_gps` ; `position()` renvoie `self._site`. Docstring : « Chaîne de position : site d'observation persisté → None ».
- `_rehydrate_alignment_once` : ne peut plus attendre un fix. La réhydratation devient un **appel direct dans le lifespan**, juste après avoir semé le site dans le bridge et construit `AlignmentServiceImpl` : si `await alignment.rehydrate()` renvoie vrai, publier `alignment` avec `is_aligned=True`. Supprimer la coroutine, sa tâche de fond et les imports devenus morts (`iter_state_snapshots` s'il n'a plus d'autre usage, `GpsState`).

- [ ] **Étape 5 : `services/alignment.py`**

Remplacer les deux appels `self._sensors.gps_fix()` (~L73 et ~L151) par `self._sensors.position()`. Mettre à jour les docstrings qui parlent de « fix GPS courant » → « position du site ». Les clés `gps_lat`/`gps_lon` du dict passé au repo **ne changent pas** (cf. Décision actée 4).

- [ ] **Étape 6 : Tests**

Réécrire `tests/test_alignment_rehydrate_trigger.py` : le déclencheur n'est plus un fix sur le bus mais le boot. Renommer en `tests/test_alignment_rehydrate_boot.py` et tester : site présent + modèle frais → `is_aligned=True` publié ; pas de site → pas de réhydratation, pas de crash.
Purger `gps` de `test_app.py`, `test_state_endpoint.py`, `test_subsystems.py`, `test_aggregator.py`, `test_fakes.py`, `test_alignment_sensors_bridge.py`, `test_alignment_service.py`.

- [ ] **Étape 7 : Suite verte + non-régression + commit**

Run: `uv run pytest -q`
Expected: PASS.
Run: `grep -rniE "gps|gpsd|latest_fix" astro_brain --include=*.py`
Expected: hits uniquement sur `gps_lat`/`gps_lon` (colonnes historiques, cf. Décision 4) et leurs commentaires. Rien d'autre.

```bash
git add -A
git commit -m "refactor(backend): retirer le GPS (gpsd, sous-système, chaîne de position)"
```

---

## Task 4 : Backend — retirer le compass LIS3MDL et toute la calibration

**Files:**
- Delete: `backend/astro_brain/adapters/lis3mdl_adapter.py`
- Delete: `backend/astro_brain/adapters/_i2c_helpers.py`
- Delete: `backend/astro_brain/routes/sensors.py`
- Delete: `backend/astro_brain/routes/calibration.py`
- Delete: `backend/astro_brain/services/calibration.py`
- Delete: `backend/astro_brain/services/_ellipsoid_fit.py`
- Delete: `backend/astro_brain/services/_heading.py`
- Delete: `backend/astro_brain/models/calibration.py`
- Delete: `backend/astro_brain/repository/calibration_repo.py`
- Delete: `backend/tests/test_lis3mdl_adapter.py`, `test_i2c_helpers.py`, `test_sensors_routes.py`, `test_calibration_routes.py`, `test_calibration_service.py`, `test_calibration_repo.py`, `test_ellipsoid_fit.py`, `test_models_calibration.py`, `test_tilt_compensated_heading.py`, `test_calibration_samples` (`tests/_calibration_samples.py`), `tests/fakes/fake_i2c.py`, `tests/fakes/sensor_fakes.py`
- Create: `backend/astro_brain/repository/migrations/_008_drop_calibration.py`
- Modify: `backend/astro_brain/services/interfaces.py` (retirer `CalibrationService` + import des modèles de calibration)
- Modify: `backend/astro_brain/deps.py` (retirer `get_calibration_service`, `get_lis3mdl`, `get_lazy_lis3mdl`)
- Modify: `backend/astro_brain/app.py` (imports, `_select_services`, lifespan, routers)
- Modify: `backend/astro_brain/services/fakes.py` (retirer `make_fake_calibration_adapters`)
- Modify: `backend/pyproject.toml` (extra `hardware` : retirer `smbus2`)
- Modify: `backend/tests/test_state_db.py`, `backend/tests/test_app.py`

**Interfaces:**
- Consumes: rien (chaîne terminale — c'est tout l'intérêt).
- Produces: plus de routes `/sensors/*` ni `/calibration/*`.

- [ ] **Étape 1 : Vérifier qu'aucun chemin métier ne lit un cap**

Run: `grep -rn "naive_heading\|heading" astro_brain --include=*.py`
Expected: hits uniquement dans `routes/sensors.py` et `services/_heading.py` — les deux fichiers supprimés ici. **Si un chemin alignement/goto lit un heading, arrêter et me le signaler** : le plan repose sur le fait que non.

- [ ] **Étape 2 : Vérifier que `ConflictError` / `SensorUnavailableError` survivent**

Run: `grep -rn "ConflictError\|SensorUnavailableError" astro_brain --include=*.py`
Expected: usages restants dans `mount_indi_adapter.py`, `routes/alignment.py`, `services/alignment.py`, `services/interfaces.py`. Ces deux exceptions **restent définies**.

- [ ] **Étape 3 : Supprimer les fichiers**

```bash
git rm astro_brain/adapters/lis3mdl_adapter.py \
       astro_brain/adapters/_i2c_helpers.py \
       astro_brain/routes/sensors.py \
       astro_brain/routes/calibration.py \
       astro_brain/services/calibration.py \
       astro_brain/services/_ellipsoid_fit.py \
       astro_brain/services/_heading.py \
       astro_brain/models/calibration.py \
       astro_brain/repository/calibration_repo.py \
       tests/test_lis3mdl_adapter.py tests/test_i2c_helpers.py \
       tests/test_sensors_routes.py tests/test_calibration_routes.py \
       tests/test_calibration_service.py tests/test_calibration_repo.py \
       tests/test_ellipsoid_fit.py tests/test_models_calibration.py \
       tests/test_tilt_compensated_heading.py tests/_calibration_samples.py \
       tests/fakes/fake_i2c.py tests/fakes/sensor_fakes.py
```

⚠️ `_LazySensor` vit dans `routes/sensors.py` et est importé par `app.py` — il part avec le fichier (aucun autre consommateur : le vérifier par grep avant de supprimer).

- [ ] **Étape 4 : Élaguer les modules partagés**

- `services/interfaces.py` : supprimer `CalibrationService`, l'import `from astro_brain.models.calibration import ...` et `AsyncIterator` s'il devient inutilisé.
- `deps.py` : supprimer `get_calibration_service`, `get_lis3mdl`, `get_lazy_lis3mdl` et `CalibrationService` de l'import.
- `services/fakes.py` : supprimer `make_fake_calibration_adapters` (et l'import `SensorUnavailableError` s'il devient inutilisé).
- `app.py` : retirer les imports `calibration_router`, `sensors_router`, `_LazySensor`, `CalibrationServiceImpl`, `make_fake_calibration_adapters`, `Lis3mdlAdapter` ; les entrées `"lis3mdl"` de `_select_services` ; les blocs `calibration_service` / `lis3mdl` / `lazy_lis3mdl` du lifespan ; les deux `include_router`.
- `pyproject.toml` : l'extra `[hardware]` se réduit à `pyindi-client>=2.0`.

- [ ] **Étape 5 : Migration `_008_drop_calibration.py`**

`VERSION = 8`, `SQL = "DROP TABLE IF EXISTS calibration_sensor;"`, docstring qui renvoie à l'ADR 2026-08-26. Sur le modèle de `_005`.

- [ ] **Étape 6 : Tests**

`tests/test_state_db.py` : `version == 8` (2 occurrences), retirer `"calibration_sensor"` de l'ensemble attendu, ajouter l'assertion `"calibration_sensor" not in tables` et un test dédié `test_migration_008_drops_calibration` calqué sur `test_migration_005_drops_mount_limits`.
`tests/test_app.py` : retirer les assertions sur les routes `/calibration` et `/sensors`, sur `app.state.lis3mdl` / `lazy_lis3mdl` / `calibration_service`.
Vérifier que `tests/fakes/__init__.py` ne ré-exporte plus rien de supprimé.

- [ ] **Étape 7 : Suite verte + non-régression + commit**

Run: `uv run pytest -q`
Expected: PASS (aucune erreur de collection).
Run: `grep -rniE "lis3mdl|calibrat|i2c|smbus|ellipsoid|magnet" astro_brain pyproject.toml`
Expected: **aucun hit**.
Run: `uv sync`
Expected: résolution OK sans `smbus2`.

```bash
git add -A
git commit -m "refactor(backend): retirer le compass LIS3MDL et la chaîne de calibration"
```

---

## Task 5 : App Flutter — carte Site d'observation, retrait GPS + compass

**Files:**
- Create: `app/lib/features/setup/site/site_screen.dart`
- Create: `app/lib/features/setup/site/site_repository.dart`
- Create: `app/test/features/setup/site/site_screen_test.dart`
- Delete: `app/lib/features/setup/calibration/` (dossier entier : `calibration_bloc.dart`, `lis3mdl_screen.dart`, `widgets/calibration_progress.dart`)
- Delete: `app/lib/models/calibration.dart`, `app/lib/models/sensor_readings.dart`
- Delete: `app/lib/services/calibration_progress_stream.dart`, `app/lib/services/compass_stream_service.dart`
- Delete: `app/test/features/setup/calibration/calibration_bloc_test.dart`, `app/test/models/calibration_test.dart`, `app/test/services/calibration_progress_stream_test.dart`, `app/test/services/compass_stream_service_test.dart`
- Modify: `app/lib/models/subsystem_kind.dart`, `subsystem_states.dart`, `system_state.dart`
- Modify: `app/lib/features/setup/setup_screen.dart`, `app/lib/features/system/system_screen.dart`, `app/lib/features/hub/hub_screen.dart`
- Modify: `app/lib/features/alignment/alignment_bloc.dart`, `alignment_repository.dart`
- Modify: `app/lib/services/api_service.dart`
- Modify: les tests correspondants (`setup_screen_test`, `subsystem_kind_test`, `subsystem_states_test`, `system_state_test`, `hub_screen_test`, `alignment_bloc_test`, `api_service_test`, `app_bloc_test`)

**Interfaces:**
- Consumes: `GET /site`, `PUT /site`, `PhoneLocation.current()`.
- Produces: carte Setup #1 « SITE », plus aucun écran compass/calibration, plus de sous-système `gps` dans l'état.

- [ ] **Étape 1 : `site_repository.dart` + `api_service`**

`SiteRepository` sur `ApiService` (`getJson('/site')`, `putJson('/site', {...})`). Ajouter `putJson` à `ApiService` s'il n'existe pas (le service a déjà `postJson`/`delete` : calquer le même traitement d'erreur). Retirer `getCalibrationStatus`, `startCalibration` et tout le reste de la surface `/calibration` + `/sensors`.

- [ ] **Étape 2 : `site_screen.dart`**

Écran Setup dédié, Material 3 / HUD, thème jour-nuit comme les autres (cf. `lib/features/setup/network/network_screen.dart` pour le gabarit) : affiche lat/lon et la date de réglage, un bouton **« Utiliser la position du téléphone »** (appelle `PhoneLocation.current()` puis `PUT /site`), et un état vide explicite (« Aucun site — l'alignement le demandera »). Pas de saisie manuelle en v1 : le besoin est de partir du GPS du téléphone.

- [ ] **Étape 3 : Carte #1 du Setup**

Dans `setup_screen.dart` : `_buildLis3mdlCard` → `_buildSiteCard` (icône `PhosphorIconsBold.mapPin`, label `SITE`, sublabel = coordonnées formatées ou « Non défini », pastille verte/grise), `_openLis3mdl` → `_openSite`, import `calibration/lis3mdl_screen.dart` → `site/site_screen.dart`, et `_lis3mdlRefresh` → `_siteRefresh`. **L'`itemCount` reste 6 et les index 2-6 ne bougent pas** — on remplace la carte 1, on ne renumérote rien (contrairement au retrait ADXL de 2026-07-17).

- [ ] **Étape 4 : Retirer le sous-système `gps` du modèle d'état**

- `subsystem_kind.dart` : retirer `gps` de l'enum.
- `subsystem_states.dart` : supprimer l'enum `GpsState` et son `fromJson`.
- `system_state.dart` : retirer le champ `gps`, sa lecture dans `fromJson` (⚠️ `subs['gps']` est un accès non-null : le laisser ferait planter au premier `/state` du nouveau backend), sa branche dans le `copyWith` par `SubsystemKind`, et l'entrée de `props`.
- `system_screen.dart` : supprimer la carte GPS (~L59-65) et les helpers `_gpsDetails` / `_gpsDot`.
- `hub_screen.dart` : la carte ALIGNER perd son bandeau « Position GPS requise — GPS Pi non disponible » (~L148-205) et son `BlocSelector` sur `state.system!.gps`. Le hint redevient statique.

- [ ] **Étape 5 : Wizard d'alignement — bascule sur `/site`**

`alignment_repository.dart` : `postClientLocation` → `putSite(lat, lon)` qui appelle `PUT /site`.
`alignment_bloc.dart` : le rattrapage du 409 reste identique (GPS téléphone → écriture → retry), seul l'appel change. Mettre à jour le commentaire L11-12 et L55 (« fallback GPS téléphone » → « écriture du site d'observation depuis le GPS du téléphone »).

- [ ] **Étape 6 : Suppressions**

```bash
git rm -r lib/features/setup/calibration \
          test/features/setup/calibration \
          lib/models/calibration.dart lib/models/sensor_readings.dart \
          lib/services/calibration_progress_stream.dart \
          lib/services/compass_stream_service.dart \
          test/models/calibration_test.dart \
          test/services/calibration_progress_stream_test.dart \
          test/services/compass_stream_service_test.dart
```

- [ ] **Étape 7 : Tests**

`site_screen_test.dart` : rendu avec site connu / inconnu, appel `PUT` sur tap du bouton (fake `PhoneLocation`, `MockBloc` si un bloc est impliqué — **ne jamais taper un bouton câblé à un vrai bloc async**, cf. mémoire projet).
Purger `gps` de `subsystem_kind_test`, `subsystem_states_test`, `system_state_test`, `hub_screen_test`, `app_bloc_test` (fixtures JSON `/state` incluses).
`setup_screen_test` : la carte 1 est « SITE ».
`alignment_bloc_test` : le mock attend `putSite` au lieu de `postClientLocation`.

- [ ] **Étape 8 : Vert + non-régression + commit**

Run: `flutter analyze`
Expected: `No issues found!`
Run: `flutter test`
Expected: PASS.
Run: `grep -rniE "gps|lis3mdl|compass|boussole|calibrat" lib test | grep -viE "geolocator|phone_location|GPS du téléphone"`
Expected: **aucun hit vivant**.

```bash
git add -A
git commit -m "feat(app): carte Site d'observation ; retrait des écrans GPS et compass"
```

---

## Task 6 : Docs vivantes + schémas

**Files:**
- Modify: `CLAUDE.md`, `README.md`
- Modify: `docs/technical/hardware.md`, `architecture.md`, `api.md`, `state-model.md`, `deployment.md`, `README.md`
- Modify: `docs/technical/cablage-capteurs-pi.html`, `cablage-global.html`, `cablage-alimentation.html`
- Modify: `docs/project/journal.md` (bullet de livraison dans la session courante)

**Interfaces:** N/A (docs de référence vivantes).

- [ ] **Étape 1 : `hardware.md`**

Supprimer la ligne d'inventaire « GPS DroTek Ublox M8N + compass XL » (~L11), la section **Bus I2C1** (~L19-51), la section **GPS — UART0** (~L53-117) *sauf* le bloc de config UART, la section **Compass LIS3MDL — I2C1** (~L119-157), et les lignes de dépannage gpsd/I2C (~L385-390).

🔴 **Le bloc `enable_uart=1` / `dtoverlay=disable-bt` / `serial-getty@ttyAMA0 disable` est CONSERVÉ** (cf. Décision actée 7) : le déplacer sous un titre neutre « UART0 (GPIO14/15) » avec une phrase disant qu'il sert désormais au pont AUX. Le plan ESP32 le reprendra tel quel.

- [ ] **Étape 2 : `architecture.md`, `state-model.md`, `api.md`**

- `architecture.md` : le schéma ASCII perd la branche « UART0 + I2C1 GPIO → DroTek GPS + LIS3MDL » ; la phrase « Pi gère la sync GPS → monture automatiquement au boot » devient « le Pi pousse le site d'observation persisté + l'heure NTP à la monture dès qu'elle est prête ».
- `state-model.md` : retirer le sous-système `gps` et son enum ; ajouter `clock_synced` aux détails de `system`.
- `api.md` : retirer `/sensors/compass/stream`, `/calibration/*`, `POST /align/location/client` ; documenter `GET /site` et `PUT /site`.

- [ ] **Étape 3 : `deployment.md`**

Retirer `indi-gpsd` de la ligne `apt install` (~L27) et `gpsd.service` du `After=` documenté. Ajouter un rappel de sauvegarde `state.db` avant le pull (les migrations `_007`/`_008` sont forward-only et `_008` est destructrice) — le paragraphe existe déjà (~L80-87), il suffit de le pointer.

- [ ] **Étape 4 : `CLAUDE.md` + `README.md` + `docs/technical/README.md`**

`CLAUDE.md` : supprimer la puce **Capteurs** (DroTek / LIS3MDL), la branche capteurs du schéma d'architecture, et la mention « sync GPS → monture au boot ». Mettre à jour la ligne Macro 2 (la calibration compass n'existe plus).

- [ ] **Étape 5 : Schémas HTML**

- `cablage-capteurs-pi.html` : **le fichier entier perd son objet** (il ne décrit que le DroTek + le LIS3MDL). Le supprimer (`git rm`) et retirer les liens qui pointent dessus (`hardware.md`, `docs/technical/README.md`, les autres HTML).
- `cablage-global.html` et `cablage-alimentation.html` : retirer les blocs / labels / lignes de conso du DroTek et du compass.

- [ ] **Étape 6 : Vérif + commit**

Ouvrir chaque HTML modifié dans un navigateur → rendu cohérent, plus aucun bloc capteur.
Run: `grep -rniE "drotek|lis3mdl|gpsd|m8n|i2c1|0x1e|compass" docs/technical CLAUDE.md README.md docs/INDEX.md | grep -viE "archive|superpowers/(specs|plans)|decisions\.md"`
Expected: **aucune mention vivante** (les ADR et le journal gardent la trace, c'est leur rôle).
Run: `grep -rn "cablage-capteurs-pi" docs .`
Expected: aucun lien pendant.

```bash
git add -A
git commit -m "docs: acter le retrait du module DroTek (docs vivantes + schémas)"
```

---

## Task 7 : Ops Pi — débrancher pour de bon

**Files:** aucun fichier du repo (hors `deploy/astro-brain.service`).
- Modify: `backend/deploy/astro-brain.service` (retirer `gpsd.service` du `After=`)

**Interfaces:** N/A.

- [ ] **Étape 1 : Sauvegarde avant migration**

Run (Pi) : `cp /var/lib/astro-brain/state.db /var/lib/astro-brain/state.db.bak-$(date +%F)`
Expected: fichier créé. `_008` est destructrice et forward-only.

- [ ] **Étape 2 : Déployer**

Run (Pi) : `cd ~/code/astro-brain && git pull && cd backend && uv sync --extra hardware && sudo systemctl restart astro-brain.service`
Expected: service `active (running)`, journal sans traceback, migrations `_007`/`_008` appliquées (`sqlite3 /var/lib/astro-brain/state.db "SELECT MAX(version) FROM schema_version"` → `8`).

- [ ] **Étape 3 : Arrêter gpsd et purger les paquets devenus inutiles**

Run (Pi) : `sudo systemctl disable --now gpsd.socket gpsd.service && sudo apt purge -y gpsd gpsd-clients indi-gpsd && sudo apt autoremove -y`
Expected: services inactifs, paquets retirés.

🔴 **NE PAS toucher** à `enable_uart=1`, `dtoverlay=disable-bt`, ni réactiver `serial-getty@ttyAMA0` : le pont ESP32 filaire les recycle (Décision actée 7). Vérifier après coup :
Run: `grep -E "enable_uart|disable-bt" /boot/firmware/config.txt; systemctl is-enabled serial-getty@ttyAMA0.service`
Expected: les deux lignes présentes, le getty `disabled`/`masked`.

- [ ] **Étape 4 : I2C — laisser en place**

Aucune action. `i2c-dev` et `dtparam=i2c_arm=on` sont inertes une fois la puce partie, et les retirer n'apporte rien de mesurable. Noter cette non-action dans le journal plutôt que de l'oublier silencieusement.

- [ ] **Étape 5 : Retrait physique**

Débrancher le module DroTek (VCC, GND, TX/RX UART0, SDA/SCL I2C1) et le sortir du boîtier. Vérifier qu'aucun fil orphelin ne traîne près du rail 5 V.
Run (Pi) : `ls -l /dev/ttyAMA0`
Expected: le périphérique existe toujours et **personne ne l'ouvre** (`sudo lsof /dev/ttyAMA0` → vide) — il est prêt pour le pont ESP32.

- [ ] **Étape 6 : Smoke test end-to-end**

Run: `curl -s http://astro-brain.local:8000/state | python3 -m json.tool`
Expected: plus de clé `gps` ; `system.details.clock_synced` présent.
Run: `curl -s -X PUT http://astro-brain.local:8000/site -H 'Content-Type: application/json' -d '{"lat":43.6,"lon":1.44}' -i`
Expected: `204`, puis `GET /site` renvoie la valeur.
Puis, monture alimentée : vérifier dans le journal que l'orchestrateur pousse bien `set_location` au passage `ready` et l'heure si l'horloge est synchronisée.

```bash
git add -A
git commit -m "chore(deploy): astro-brain.service ne dépend plus de gpsd"
```

---

## Self-Review (exécutée à la rédaction)

- **Couverture périmètre** : socle site (Task 1), orchestrateur + horloge (Task 2), GPS (Task 3), compass + calibration (Task 4), app Flutter (Task 5), docs et schémas (Task 6), Pi et retrait physique (Task 7). ✅
- **Ordre de dépendances** : l'additif précède le soustractif — le site existe (T1) avant que l'orchestrateur ne s'y adosse (T2), qui précède la disparition du GPS (T3), elle-même indépendante du compass (T4). Chaque tâche est déployable seule. ✅
- **Pièges couverts** : `_LazySensor` importé depuis `routes/sensors.py` (T4 étape 3) ; `SensorUnavailableError`/`ConflictError` partagés avec la monture et le wizard (Global Constraints + T4 étape 2) ; `subs['gps']` non-null côté Flutter qui planterait au premier `/state` (T5 étape 4) ; `Orchestrator` construit hors lifespan alors que le bridge est construit dedans (T2 étape 4) ; garde ΔGPS 20 m contre la gigue du GPS téléphone (Décision actée 3) ; `enable_uart`/`disable-bt`/getty conservés pour le plan suivant (Décision 7, rappelé en rouge dans T6 et T7) ; migrations forward-only et sauvegarde `state.db` (T7 étape 1). ✅
- **Placeholders** : aucun TODO/TBD ; chaque tâche a un critère vert et un grep de non-régression. ✅
- **Numéros de ligne** : indicatifs (« ~L… ») au moment de la cartographie ; l'implémenteur confirme dans la source avant d'éditer.
- **Hors périmètre assumé** : pré-pointage automatique des étoiles #2/#3 (backlog + roadmap Macro 3), horloge RTC DS3231 (backlog), observation hors WiFi domestique (backlog).

## Décision ouverte (une seule)

**Sonde d'horloge** : le choix entre `/run/systemd/timesync/synchronized` (gratuit, `systemd-timesyncd`) et `timedatectl show --property=NTPSynchronized` (sous-processus, `chrony`) dépend de ce qui tourne réellement sur le Pi — d'où l'étape 0 de la Task 2, à exécuter **sur le Pi** avant d'écrire l'adapter. Aucun autre point n'est ouvert.
