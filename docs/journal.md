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

### Prochaine session
- Task 5 : `Protocol` interfaces des services + fakes programmables (mount, gps, tracking, network, system).
