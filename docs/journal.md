# Journal de sessions - Astro-Brain DIY

## 2026-04-15 - Session 1 : Initialisation du projet

- Lecture de la documentation d'architecture hardware/software
- Création du `CLAUDE.md` avec la description du projet, la stack et les conventions
- Création du journal de sessions (`docs/journal.md`)
- Le projet est au stade de conception : la feuille de route est posée, pas encore de code

## 2026-04-15 / 2026-04-16 - Session 2 : Brainstorm et design v0.1

### Décisions d'architecture
- **Arduino retiré** de l'architecture : le Pi communique directement avec la monture, pas besoin d'intermédiaire
- **Port HC** (RS-232, protocole NexStar) choisi pour la communication monture — on remplace la raquette
- **nexstarpy** comme driver monture (protocole NexStar v1.2 complet)
- **REST uniquement** pour la v0.1 (pas de WebSocket) — le D-Pad fonctionne en start/stop
- **App Flutter native** sur téléphone (pas une PWA servie par le Pi)
- Le Pi gère la **sync GPS → monture automatiquement** au boot — l'app ne fait que lire l'état

### Design UI
- Style **HUD spatial** avec thème double : bleu (jour) / rouge (nuit, préservation vision nocturne)
- Un seul écran : status bar, télémétrie, D-Pad + slider vitesse, toggle tracking
- Switch jour/nuit dans la status bar
- Mockups validés via visual companion

### Matériel
- T7C pour l'imagerie principale (disponible)
- **Orion StarShoot Autoguider commandée** (40€) — plate solving + futur guidage
- **SVBONY SV165** choisie comme lunette guide
- PiCam écartée (problème de nappe rigide sur tube mobile)

### Roadmap définie
- v0.1 → v0.5, du joystick basique jusqu'au module astrophoto complet

### Config dev
- VS Code Remote-SSH configuré vers le Pi (astro-brain / pascal3100)
- Contexte 1M désactivé dans settings.json Claude Code

### Livrables
- Spec design v0.1 : `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md`
- CLAUDE.md mis à jour avec la nouvelle architecture

### Setup Pi
- Pi OS 64-bit Lite, install brute
- VS Code Remote-SSH configuré (astro-brain / pascal3100)
- `apt install python3-pip python3-venv gpsd gpsd-clients`
- venv créé : `~/astro-brain`
- Packages installés dans le venv : fastapi, uvicorn, nexstarpy, gpsd-py3, pyserial
- Contexte 1M désactivé dans settings.json Claude Code

### Prochaine session
- Écrire le plan d'implémentation v0.1
- Inspecter l'API nexstarpy sur le Pi (Python 3.13 disponible)
- Commencer l'implémentation

## 2026-04-18 - Session 3 : Setup repo, alignement dev env, plan backend recalé

### Infra
- **mDNS installé sur le Pi** (`avahi-daemon`) : `astro-brain.local` résolvable même si l'IP bouge côté box. Résout le problème de SSH cassé entre sessions quand le Pi a redémarré.
- Reco donnée : compléter avec une réservation DHCP côté box (pas encore faite).

### Décision — Workflow de dev hybride
Retour en arrière sur la décision précédente "dev directement sur le Pi via VS Code Remote-SSH" :
- Pi 3 B+ (1 GB RAM, SD card) = VS Code Server trop lent, risque d'OOM
- Claude Code tourne sur le workstation → SSH pour chaque Read/Edit = friction permanente
- **Adopté** : édition + tests pur-logique sur le workstation, exécution hardware sur le Pi, git = source de vérité unique. Sur le Pi : `git pull && uv run uvicorn ...`.

### Décision — Python & tooling
- Python aligné à **3.13** côté workstation (pour matcher le Pi, éviter les dérives)
- **`uv`** retenu comme gestionnaire Python/venv/lockfile (vs pip + venv manuel)
- `uv.lock` commité pour reproductibilité
- Deps hardware (`nexstarpy`, `gpsd-py3`, `pyserial`) isolées dans l'extra `[hardware]` → absentes du venv local, installées sur le Pi via `uv sync --extra hardware`

### Décision — Layout monorepo
- Arbitrage A (monorepo) vs B (flat) → **A retenu**
- `backend/` contient pyproject.toml, uv.lock, .python-version, .venv, `astro_brain/`, `tests/`
- `app/` viendra à côté pour Flutter (plan 2)
- `docs/` et config globale restent à la racine

### Setup repo
- `git init` + rename `master` → `main`
- Initial commit : CLAUDE.md + docs + config
- Remote `Pascal3100/astro-brain` (déjà créé, vide) connecté, push OK
- 2e commit : déplacement des fichiers Python dans `backend/`, ajout de `sse-starlette`, renommage projet en `astro-brain-backend`, build-system setuptools pour garder la compat `pip install -e` si besoin

### Plan backend recalé
- `docs/superpowers/plans/2026-04-17-astro-brain-v01-backend.md` : Task 0 (monorepo init, GitHub, venv) **supprimée** car entièrement faite. Task 1 **réécrite** — ne reste que : `README.md` racine, `backend/README.md` (adapté uv), smoke test `test_package.py`, clone sur le Pi, commit.
- File Structure du plan mise à jour (`✅ done` pour ce qui est en place).

### Docs & mémoire
- `CLAUDE.md` aligné : architecture (REST + SSE explicite), nouvelle section "Structure du repo", nouvelle section "Workflow de dev" (uv, hybride, git source de vérité), conventions (plans + journal comme fil rouge).
- Mémoire persistante : `project_dev_workflow` corrigé (hybride), nouveau `feedback_session_journal` (tenir le journal à jour régulièrement).

### Task 1 du plan backend — bouclée
- `README.md` racine (intro projet, structure monorepo, roadmap)
- `backend/README.md` (setup `uv`, run local avec fakes, run sur Pi avec `--extra hardware`)
- `backend/tests/test_package.py` : smoke test d'import — passe (`1 passed in 0.01s`)
- Clone du repo sur le Pi à `~/code/astro-brain/`, synchronisé via `git pull`

### Infra Pi complétée en passant
- `git` installé sur le Pi (Pi OS Lite n'en avait pas)
- Clé SSH ed25519 générée sur le Pi, ajoutée à GitHub via `gh ssh-key add` (a nécessité un `gh auth refresh -s admin:public_key` côté workstation)
- Le Pi clone désormais en SSH (`git@github.com:...`), pas besoin de gestion HTTPS/PAT

### Prochaine session
- Task 2 : modèles `SubsystemState` / `SystemState` + enums + sérialisation, en TDD

## 2026-04-19 - Session 4 : Task 2 (modèles d'état), TDD

### Décision — Best practices Python
- Règle de session : tout code Python doit respecter les PEPs (PEP 8, PEP 257 docstrings, PEP 484/604 type hints modernes `X | None`, `from __future__ import annotations`, imports triés stdlib/tiers/local).
- Mémoire persistante `feedback_python_peps` ajoutée.

### Task 2 du plan backend — bouclée
TDD, cycle red → green suivi strictement.
- `backend/astro_brain/subsystems.py` : 5 string enums (`MountState`, `GpsState`, `TrackingState`, `NetworkState`, `SystemInfoState`) + dataclass frozen `SubsystemState` (state, details, since, message) avec `to_dict()`.
- `backend/astro_brain/system_state.py` : dataclass frozen `SystemState` (overall, subsystems, seq, ts) avec `to_dict()`.
- `backend/tests/test_subsystems.py` : 9 tests (enums, roundtrip, sérialisation). Tous verts.
- Suite complète backend : 10/10 passent (`uv run pytest`).
- Commit `feat(backend): add subsystem state enums and SystemState model` poussé.

### Task 3 du plan backend — bouclée
- `backend/astro_brain/aggregator.py` : fonction pure `compute_overall(subsystems)` qui applique les règles du spec (rouge si `mount` disconnected/error ; bleu si n'importe quel sous-système en transient ; orange si dégradé ; vert sinon). Constantes `CRITICAL_SUBSYSTEMS`, `FATAL_STATES`, `TRANSIENT_STATES`, `DEGRADED_STATES` exposées (frozensets).
- `backend/tests/test_aggregator.py` : 11 tests couvrant matrix de priorité (red>blue>orange>green) et cas non critiques (gps, network, system) qui ne font que dégrader.
- Suite complète : 21/21 verts.
- Commit `feat(backend): add aggregator computing overall system color` poussé.

### Décision — Mode apprentissage
- Règle de session : expliquer de façon synthétique les concepts Python/asyncio/FastAPI à chaque étape non triviale, avant de coder. Mémoire persistante `feedback_learning_mode`.

### Task 4 du plan backend — bouclée
- `backend/astro_brain/bus.py` : classe `StateBus` en mémoire. `publish(subsystem, state)` synchrone et non-bloquant : mute l'état, `seq += 1`, recalcule `overall`, broadcast un `Event(type="update")` dans chaque `asyncio.Queue` d'abonné (drop-oldest si queue pleine). `subscribe()` = async generator qui yield d'abord un `Event(type="snapshot")` puis boucle sur les updates. `finally` désabonne au `aclose()`.
- `Event` = dataclass `{type, payload}` — enveloppe typée au-dessus du dict JSON.
- `backend/tests/test_bus.py` : 8 tests (état initial, incrément seq, recalcul overall, snapshot à la connexion, diffusion multi-abonnés, désabonnement propre, dataclass Event). Timeouts `asyncio.wait_for(..., 1.0)` partout pour éviter les freezes.
- Suite : 29/29 verts.
- Commit `feat(backend): add in-memory StateBus with pub/sub and snapshot` poussé.

### Task 5 du plan backend — bouclée
- `backend/astro_brain/services/interfaces.py` : 5 `typing.Protocol` (MountService, TrackingService, GpsService, NetworkService, SystemInfoService) — structural typing PEP 544, pas d'héritage requis côté implémentations. `Axis = Literal["alt", "az"]` et `Direction = Literal["+", "-"]` (PEP 586).
- `backend/astro_brain/services/fakes.py` : 5 fakes programmables (FakeMount, FakeTracking, FakeGps, FakeNetwork, FakeSystemInfo). Chacun reçoit le `StateBus` au constructeur (DI) et publie des `SubsystemState` déterministes. Kwargs keyword-only (PEP 3102) pour la config des fakes (lat/lon/état initial…).
- `backend/tests/test_fakes.py` : 9 tests couvrant publication initiale, transitions (slew → moving, stop_slew → ready), seuils thermiques.
- Suite : 38/38 verts.
- Commit `feat(backend): add service interfaces and fake implementations` poussé.

### Task 6 du plan backend — bouclée
- `backend/astro_brain/api_models.py` : 4 Pydantic models (`SlewRequest`, `StopRequest`, `TrackingRequest`, `OkResponse`) avec validation déclarative (`Field(ge=1, le=9)`, `Literal[...]`). Pydantic v2 déjà présent via FastAPI → aucune dep à ajouter.
- Pas de test dédié — ces modèles seront exercés indirectement par les tests des routes (Task 7+).
- Smoke check manuel : instanciation OK, `rate=10` et `axis="x"` rejetés avec `ValidationError`.
- Suite : 38/38 verts.
- Commit `feat(backend): add Pydantic API models for REST commands` poussé.

### Task 7 du plan backend — bouclée
- `backend/astro_brain/deps.py` : registre DI module-level. Six callables `get_bus`/`get_mount`/`get_tracking`/`get_gps`/`get_network`/`get_system_info` initialisés à `_not_wired` qui lève `RuntimeError` — force le fail-fast si le wiring manque. L'app `build_app()` (Task 11) les rebindera.
- `backend/astro_brain/routes/commands.py` : `APIRouter` avec trois POST (`/slew`, `/stop`, `/tracking`). Handlers async, body validé via Pydantic (Task 6), `response_model=OkResponse` pour le contrat de sortie.
- `backend/tests/test_commands.py` : 6 tests avec `TestClient` FastAPI. Fixture rebinde `deps.get_*` vers des fakes + restaure le binding précédent en teardown (hygiène, évite les fuites entre tests).
- Suite : 44/44 verts.
- Commit `feat(backend): add REST command endpoints (/slew /stop /tracking)` poussé.

### Task 8 du plan backend — bouclée
- `backend/astro_brain/routes/state.py` : `APIRouter` minimal avec un seul `GET /state` qui retourne `deps.get_bus().get_full_state().to_dict()`.
- `backend/tests/test_state_endpoint.py` : 2 tests (bus vide → `overall=green seq=0 subsystems={}` ; après publish → subsystems peuplés, `seq=2`). Fixture avec restore de `deps.get_bus` en teardown.
- Suite : 46/46 verts.
- Commit `feat(backend): add GET /state endpoint` poussé.

### Task 9 du plan backend — bouclée
- `backend/astro_brain/routes/events.py` : `GET /events` branché sur `StateBus.subscribe()` via `sse-starlette`'s `EventSourceResponse`. Check `request.is_disconnected()` à chaque itération, ping auto toutes les 15 s (keep-alive contre les proxies).

### Décision — Stratégie de test SSE
Le plan prévoyait un test end-to-end via `httpx.AsyncClient + ASGITransport`. **Bloque** : `httpx.ASGITransport` (et `FastAPI TestClient`) bufferisent toute la réponse avant de la livrer — incompatible avec un stream SSE infini. Le test restait pendu sur `c.stream(...)` jusqu'à timeout.
- Arbitrage : plutôt que sortir uvicorn en thread (overkill pour 1 test), **tester le handler directement** en itérant `response.body_iterator`. Ce dernier est notre propre async-gen → on assert la forme des dicts émis sans passer par la sérialisation bytes de sse-starlette (qui est testée par sa propre suite).
- 2 tests : (1) snapshot + update après un publish, (2) pas d'émission si client déjà déconnecté (retourne `StopAsyncIteration`). Mock du `Request` via `AsyncMock(is_disconnected=...)`.

- Suite : 48/48 verts.
- Commit `feat(backend): add SSE /events endpoint streaming StateBus events` poussé.

### Task 10 du plan backend — bouclée
- `backend/astro_brain/orchestrator.py` : première brique *consommatrice* du bus. `Orchestrator.run()` s'abonne via `StateBus.subscribe()` puis, à chaque événement, relit l'état complet et appelle `_maybe_sync()`. Critère : `mount = ready` **ET** `gps ∈ {fix_2d, fix_3d}` **ET** `details.lat/lon` non-null → `await mount.set_time(iso_utc)` puis `await mount.set_location(lat, lon)` **une seule fois**.
- Machine à états **edge-triggered** (pas level-triggered) : flag `_synced` armé quand la sync réussit, réinitialisé dès que les conditions retombent. Un `gps` republié avec plus de satellites mais mêmes lat/lon ne redéclenche pas de sync — seule une vraie transition out→in le fait. Sémantique qui évite de spammer la monture à chaque ping GPS.
- `backend/tests/test_orchestrator.py` : 4 tests async avec `unittest.mock.AsyncMock` côté mount. Helpers `_run_briefly` (lance la task + `sleep(0.05)` pour laisser le premier snapshot passer) et `_stop_task` (cancel + attend la `CancelledError` — hygiène de teardown). Couvre : (1) sync quand mount=ready après gps=fix_3d, (2) pas de sync si gps=no_fix, (3) une seule sync pendant que les conditions tiennent, (4) resync après disconnect+reconnect du mount.
- Suite : 52/52 verts.
- Commit `feat(backend): add orchestrator that syncs mount with GPS on boot` poussé.

### Task 11 du plan backend — bouclée
- `backend/astro_brain/app.py` : `build_app(use_hardware: bool | None = None)` construit un `FastAPI` neuf à chaque appel (un `StateBus` + 5 services + orchestrateur par instance → isolation test). `_select_services` retourne les fakes par défaut, ou les adapters hardware (imports locaux *inside the branch* → pas d'`ImportError` tant que Tasks 12–15 pas faites). Fallback sur `ASTRO_BRAIN_HARDWARE=1` si `use_hardware` pas passé.
- **Lifespan async context manager** (remplace les `@on_event("startup"/"shutdown")` deprecated). Avant `yield` : `await services[*].start()` (chaque fake publie son état initial → mount=ready, gps=fix_3d, network=client, system=ok) puis `asyncio.create_task(orchestrator.run(), name="orchestrator")`. Après : `task.cancel()` + `contextlib.suppress(CancelledError)` pendant `await task` (cleanup propre sans que asyncio ne râle), puis `stop()` sur chaque service.
- `backend/astro_brain/main.py` : `from astro_brain.app import app` pour exposer l'app à uvicorn. `run()` lit `ASTRO_BRAIN_HOST/PORT` depuis l'env et lance `uvicorn.run("astro_brain.main:app", ...)`.
- `backend/tests/test_app.py` : 2 tests end-to-end avec `TestClient`. (1) `GET /state` après startup → mount.state == "ready" et gps.state == "fix_3d". (2) Flux `slew` → `state` (moving) → `stop` → `state` (ready). `TestClient` gère le lifespan automatiquement via le context manager.
- Suite : 54/54 verts.
- Smoke uvicorn (`uv run uvicorn astro_brain.main:app --host 127.0.0.1 --port 8765`) : `/state` renvoie les 5 subsystems (overall=green), `POST /slew` → `{"ok":true}` + mount=moving, `/events` émet `event: snapshot` avec le payload JSON attendu.
- Commit `feat(backend): wire application with fakes, orchestrator, and lifecycle` poussé.

### Task 12 du plan backend — bouclée
- `backend/astro_brain/adapters/__init__.py` + `system_info.py` : premier adapter hardware. Lit `/sys/class/thermal/thermal_zone0/temp` (milli-°C, divise par 1000), `/proc/uptime` (1er champ), `/proc/loadavg` (1er champ = moyenne 1 min). Thresholds : `WARN_TEMP_C=70`, `CRIT_TEMP_C=80` (le Pi 3 B+ throttle à ~82°C), `WARN_LOAD=1.5`.
- `compute_state(temp, load)` = fonction pure → classification `ok` → `warning` → `critical`. Critical temp override le load (cas "CPU brûle même si load faible").
- Loop async `_loop()` : `asyncio.sleep(5)` + `_publish_current()`. `except asyncio.CancelledError: return` pour arrêt propre, `except OSError: continue` pour rester vivant si une lecture sysfs foire transitoirement (robustesse sans bruit dans les logs).
- Pas de tests FS (conformément au plan — mocks trop lourds pour ce qu'ils apporteraient, couvert par smoke manuel sur Pi). Par contre 5 tests unitaires sur la fonction pure `compute_state` (aucun mock nécessaire) : couvre les 3 états + les 2 conditions de warning + priorité critical sur load.
- Duck typing : l'adapter n'hérite pas de `SystemInfoService` mais expose les mêmes méthodes → `build_app(use_hardware=True)` pourra le swap-in là où `FakeSystemInfo` était (PEP 544).
- Suite : 59/59 verts (ajout de 5 tests).
- Commit `feat(backend): add SystemInfo adapter (sysfs CPU temp + loadavg)` poussé.

### Task 13 du plan backend — bouclée
- `backend/astro_brain/adapters/network_info.py` : polling 5 s via `subprocess.check_output(["ip", "-4", "-o", "addr", ...])` et `iwgetid -r <iface>` + lecture directe de `/sys/class/net/<iface>/operstate`. Interface par défaut `wlan0` (surchargeable via kwarg `interface=`).
- **Throttling par diff** : `_last: tuple[str, dict] | None` mémorise le (state, details) précédent ; `_publish_current` skip le publish si identique. Différent du SystemInfo adapter où temp/load/uptime bougent constamment → on publie toujours (traite l'état complet sur chaque tick). Ici SSID + IP sont stables → publier à chaque tick serait du bruit sur le bus.
- Détection `hotspot` : SSID qui commence par `astro-brain` → le Pi est son propre AP (mode setup initial, sans Wi-Fi). Sinon `client` (connecté à un réseau Wi-Fi externe) ou `offline` (interface down ou absente).
- `except OSError: continue` dans la loop pour rester vivant si une commande shell foire transitoirement — `CalledProcessError`/`FileNotFoundError` sont déjà attrapés dans les helpers (pas besoin de les propager jusqu'à la boucle).
- Pas de tests unitaires (conformément au plan — trop d'I/O à mocker, couvert par smoke sur Pi via la checklist Task 17).
- Suite : 59/59 verts (pas de test ajouté).
- Commit `feat(backend): add NetworkInfo adapter (sysfs + iwgetid)` poussé.

### Task 14 du plan backend — bouclée
- `backend/astro_brain/adapters/gpsd_adapter.py` : consomme le daemon `gpsd` via `gpsd-py3` (dep `hardware` extra, pas installée sur la workstation). **Import lazy** de `gpsd` à l'intérieur de `start()` et `_loop()` → le module reste importable sans la dep ; seul le `.start()` échouerait. Vérifié : `from astro_brain.adapters.gpsd_adapter import GpsdAdapter` OK sur la workstation sans l'extra.
- `mode_to_state(mode, sats)` = fonction pure. gpsd `mode` : 2 → `fix_2d`, 3 → `fix_3d`. Si `mode < 2` mais `sats > 0` → `searching` (antenne capte mais pas encore assez). Sinon `no_fix`. 5 tests unitaires couvrent les 4 états.
- **Polling à 2 Hz, publish throttled à 1 Hz** sur les détails (lat/lon/altitude/hdop changent en permanence → éviter de spammer le bus). Règle : `state_changed or detail_ready` où `detail_ready = now - last_detail_publish >= 1s`. Transitions d'état sont toujours publiées immédiatement.
- Packet parsing défensif : `getattr(packet, "sats", 0) or 0` pour gérer les `None`. `contextlib.suppress(Exception)` autour de `packet.position()` et `.altitude()` qui raise chez gpsd-py3 quand pas de fix. `except Exception: continue` dans la boucle pour garder l'adapter vivant face aux transients — perte de sémantique acceptable vu la complexité du parsing gpsd.
- Suite : 64/64 verts (5 nouveaux tests).
- Commit `feat(backend): add Gpsd hardware adapter (DroTek, via gpsd-py3)` poussé.

### Décision d'archi — GPS en UART GPIO plutôt qu'en USB
- Le module DroTek (Ublox M8N + compass magnétique) expose **les deux interfaces** : un micro-USB (natif u-blox) et des broches UART+I2C. CLAUDE.md et `architecture_hardware.txt` prévoyaient l'USB.
- **Revirement** : basculer sur GPIO (UART0 pour le GPS, I2C1 pour le compass). Motif : les 4 ports USB du Pi 3 B+ doivent rester libres pour la monture (déjà USB-série) + les caméras (v0.5). Le compass n'est **pas** accessible via USB (seul le GPS l'est), donc l'utiliser un jour imposerait de toute façon un branchement GPIO partiel — autant tout câbler d'un coup.
- **Impact code** : zéro. `GpsdAdapter` parle au daemon `gpsd`, pas au `/dev/tty*` direct. Seule la config gpsd sur le Pi change (`DEVICES=/dev/serial0` au lieu de `/dev/ttyACM0`).
- **Impact config Pi** : activer UART hardware + `dtoverlay=disable-bt` (pour libérer le vrai PL011 du Bluetooth sur Pi 3 B+, timing plus stable que le mini-UART), activer I2C, configurer `/etc/default/gpsd`. À intégrer dans le script d'install (Task 16).
- **Câblage** : 6 fils dupont — détails complets dans `docs/hardware_wiring.md` (plan du header, tables GPS + compass, vérifications `dmesg`/`cat /dev/serial0`/`gpsmon`/`i2cdetect`, dépannage).
- `CLAUDE.md` et `docs/architecture_hardware.txt` mis à jour pour pointer vers `hardware_wiring.md`.

### Prochaine session
- Task 15 : `NexStarMountAdapter` (monture Celestron via `nexstarpy` sur USB-série `/dev/ttyUSB0`). Expose toutes les méthodes de `MountService` (slew/stop_slew/set_time/set_location/set_tracking_mode). Publie `connecting → ready → moving/ready`, watchdog 2 s via `get_version()` pour détecter déconnexions.

## 2026-04-20 - Session 5 : Brainstorm réflexions v0.2+ + Task 15

Session dédiée à capturer des idées pour l'après-v0.1 : réglages techniques monture, configuration caméras, position persistante / home avec piste IMU, arrêt d'urgence, logs persistants, automatisation ops (systemd + déploiement), mode "mise en station".

Création de `docs/backlog.md` pour héberger ces réflexions transverses — le journal n'est pas le bon endroit pour ce type de contenu. Le backlog est référencé depuis `CLAUDE.md`.

### Task 15 du plan backend — bouclée
- `backend/astro_brain/adapters/nexstar_adapter.py` : adapter hardware pour la monture Celestron via `nexstarpy` (extra `[hardware]`). **Import lazy** de `nexstarpy` dans `start()` → module reste importable sur workstation sans l'extra. Même pattern que `GpsdAdapter` (Task 14).
- Lifecycle : `connecting` publié immédiatement, puis `ready` (avec `firmware_version` dans `details`) si `NexStar(device).get_version()` réussit, sinon `error` avec `message=str(exc)`. `stop()` cancelle le watchdog, ferme le client, publie `disconnected`.
- **Watchdog** : `asyncio.Task` nommé `mount-watchdog` créé dans `start()`, fait un `get_version()` toutes les 2 s. Sur `CancelledError` → sort propre. Sur toute autre exception → publie `mount=error` et termine (pas de spam de la boucle). Idem pattern Orchestrator Task 10.
- Commandes : `slew`/`stop_slew` avec try/except par appel (une commande foireuse publie `error` sans tuer l'adapter). `stop_slew(axis=None)` cycle sur `("alt","az")` et vide `_active_slews`. Republie l'état `moving` ou `ready` selon la liste des slews restants.
- `set_time(utc_iso)` : `datetime.fromisoformat` → tuple 8-entiers NexStar `(year, month, day, hour, minute, second, 0, 0)` (UTC offset + DST à 0 car orchestrateur envoie toujours de l'UTC).
- `set_tracking(enabled)` : `TRACKING_MODE_SIDEREAL = 1` extrait en constante (valeur à valider sur vrai firmware en Task 17 — certaines versions mappent autrement). Publie sur `tracking`, pas sur `mount`.
- **Archi : un objet, deux Protocoles** (duck typing, PEP 544). `NexStarMountAdapter` implémente à la fois `MountService` et `TrackingService`. Dans `app.py` branche hardware, la **même instance** est stockée sous les clés `"mount"` et `"tracking"` → `/tracking` drive la vraie monture sans code additionnel. Cohérent avec le fait que le tracking sidéral est une commande monture, pas un sous-système séparé.
- Pas de tests unitaires (conformément au plan — adapter hardware couvert par Task 17 sur le Pi).
- Suite : 64/64 verts. Import `NexStarMountAdapter` OK sur workstation sans `nexstarpy`.
- Commit `feat(backend): add NexStar mount adapter and wire it as tracking service` poussé.

### Task 16 du plan backend — bouclée
- `backend/deploy/astro-brain.service` : unit systemd. `After=network-online.target gpsd.service`, `Wants=network-online.target`, `User=pascal3100`, `WorkingDirectory=/home/pascal3100/code/astro-brain/backend`, env `ASTRO_BRAIN_HARDWARE=1`, `ExecStart=.venv/bin/uvicorn astro_brain.main:app --host 0.0.0.0 --port 8000`, `Restart=on-failure`.
- `backend/deploy/install.sh` : **divergence plan → uv**. Le plan prévoyait `pip install -e '.[hardware,dev]'` ; on a gardé `uv sync --extra hardware` pour rester cohérent avec le reste du projet (lockfile reproductible workstation↔Pi). Plan Step 16.2 mis à jour en conséquence. Le script détecte l'absence de `uv` en PATH et bail avec le lien d'install.
- **Setup Pi** : `uv` manquait (jamais installé en Session 2/3, la journal décrivait le workflow cible sans l'avoir exécuté). Installé user-space via `curl -LsSf https://astral.sh/uv/install.sh | sh`. Puis `bash deploy/install.sh` → venv créée, deps hardware installées, service enabled + started. `sudo systemctl --no-pager status astro-brain` → `active (running)`.
- **Smoke test** `curl http://astro-brain:8000/state` : `overall=red` (cohérent, car monture pas branchée → `mount=error` avec `message=[Errno 2] could not open port /dev/ttyUSB0`). `network=client SSID=Chez_nous_ou_pas IP=192.168.1.36`, `system=ok cpu_temp=52°C load=0.12 uptime=951s`. GPS = `no_fix` avec `details={}` — gpsd non encore configuré pour `/dev/serial0` (config `dtoverlay=disable-bt` + `/etc/default/gpsd` à faire en Task 17).

### Fix en passant — tracking subsystem manquant en mode hardware
- Bug introduit en Task 15 : `NexStarMountAdapter` réutilisé comme tracking service ne publiait `"tracking"` que dans `set_tracking()`. Résultat : tant que `/tracking` n'avait pas été appelé, le sous-système `tracking` était absent de `/state` (alors que `FakeTracking` le publiait dès son `__init__`).
- Fix : publish `tracking=off` dans `start()` du NexStar adapter, **après** la connexion monture réussie (pas dans la branche `except` — si la monture est injoignable on ne connaît pas l'état réel du tracking, mieux vaut l'omettre qu'inventer).
- Commit `fix(backend): publish initial tracking=off when NexStar adapter connects` poussé, service redémarré sur le Pi.
- Observation : `tracking` reste absent tant que `/dev/ttyUSB0` n'existe pas — attendu. Re-validation nécessaire quand la monture sera branchée.

### Apprentissages Session 5
- Différence `pip install -e .[extra]` vs `uv sync --extra extra` : le 1er ignore le lockfile (dérive possible), le 2nd l'impose (reproductible). Le choix `uv` est critique pour garantir workstation et Pi sur les mêmes versions exactes des deps hardware.
- Pattern "un objet, deux Protocoles" (PEP 544) : `NexStarMountAdapter` implémente `MountService` **et** `TrackingService`, même instance sous deux clés dans le dict services. Cohérent avec le fait que tracking = commande monture, mais impose de publier l'état initial sur **les deux** canaux du bus (le bug fixé ci-dessus).
- Hygiène systemd : `Type=simple` + `Restart=on-failure` + `User=<non-root>` + `WorkingDirectory=` absolu + `Environment=` explicite → le service est auto-documenté et survit aux crashes.

### Task 17 du plan backend — stub créé
- `backend/deploy/INTEGRATION_CHECKLIST.md` : checklist manuelle à cocher lors de la prochaine session physique sur le Pi. Divergence vs plan : ajout d'une **section 0 Prérequis Pi-level** en amont (dtoverlay UART/I2C dans `/boot/firmware/config.txt`, `disable-bt`, config `/etc/default/gpsd`, groupe `dialout` pour pascal3100) — pas couvert par `install.sh` et c'est un one-shot. Référence `docs/hardware_wiring.md` pour le câblage plutôt que de dupliquer.
- Host remplacé `astro-brain.local` → `astro-brain` (mDNS ne résout pas toujours côté workstation, le DNS local via box résout `astro-brain.lan`).
- Note explicite pointant vers `TRACKING_MODE_SIDEREAL` dans `nexstar_adapter.py` si le sidéral ne s'engage pas (firmware différent → essayer 2 ou 3).
- **Step 17.3 (dérouler la checklist)** = session physique, pas faisable ce soir. À faire une fois la monture branchée + gpsd configuré. Les findings seront ajoutés au journal comme "Session 6 — checklist d'intégration".
- Commit `docs(backend): add manual hardware integration checklist` poussé.

### Plan backend v0.1 — COMPLET côté code 🎉
Toutes les tasks du plan `docs/superpowers/plans/2026-04-17-astro-brain-v01-backend.md` sont bouclées côté livrable code/doc. Backend complet :
- 5 sous-systèmes publiant sur un bus pub/sub in-memory (StateBus, Task 4)
- Aggregator déterministe calculant `overall` green/blue/orange/red (Task 3)
- Orchestrateur edge-triggered qui synchronise monture ↔ GPS sur boot (Task 10)
- REST endpoints `/slew` `/stop` `/tracking` `/state` + SSE `/events` (Tasks 7-9)
- Fakes (workstation) + adapters hardware réels (Tasks 12-15) derrière les mêmes Protocols
- Orchestration `build_app()` + lifespan async (Task 11)
- systemd + install.sh + checklist d'intégration (Tasks 16-17)
- 64 tests automatisés verts. Hardware path : checklist manuelle pour validation physique.
- Service `active (running)` sur le Pi, reachable via `curl http://astro-brain:8000/state`.

### Prochaine session
- **Session 6 (physique)** : dérouler `backend/deploy/INTEGRATION_CHECKLIST.md` sur le Pi — câblage GPS UART + compass I2C, config gpsd, connexion monture, vérifier les 7 sections. Fixer les divergences en commits ad-hoc. Noter les findings en bas du doc + dans le journal.
- **Plan 2 (app Flutter)** : à rédiger une fois la v0.1 backend validée physiquement. Design HUD spatial déjà speccé en Session 2.
