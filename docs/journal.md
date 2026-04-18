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

### Prochaine session
- Exécuter Task 1 : READMEs, smoke test, clone du repo sur le Pi
- Enchaîner sur Task 2 (modèles `SubsystemState` / `SystemState`)
