# Astro-Brain DIY

## Description du projet

Système de contrôle autonome pour télescope Maksutov Bresser 127/1900 sur monture Celestron. Le Raspberry Pi pilote la monture via un pont ESP32 (WiFi ↔ bus AUX) et sert de backend pour une app Flutter sur téléphone.

## Documentation

**Point d'entrée unique** : [`docs/INDEX.md`](docs/INDEX.md) — référence trois vues `technical/`, `project/`, `product/`.

- **Technique** ([`docs/technical/`](docs/technical/README.md)) : architecture, hardware/wiring, modèle d'état, API, déploiement.
- **Projet** ([`docs/project/`](docs/project/README.md)) : roadmap, ADRs (`decisions.md`), journal (`journal.md`), backlog (`backlog.md`).
- **Produit** ([`docs/product/`](docs/product/README.md)) : design system, fiches features.

Specs et plans : `docs/superpowers/specs/` et `docs/superpowers/plans/`.

## Stack technique

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+
- **Frontend** : App Flutter native sur téléphone (pas une PWA), pattern BLoC
- **Communication Pi <-> Monture** : stack INDI (`indiserver` + driver `indi_celestron_aux`) côté Pi, client Python `pyindi-client` dans le backend FastAPI. Liaison physique : port **HAND CONTROL** (RJ-12 6P6C) de la base SLT — sur le **bus AUX** interne, raquette hors boucle → interface single-wire (RX LM2902 / TX 74AHCT125) → **pont ESP32** exposant le bus en **TCP port 2000** (WiFi), driver en **mode Network** (`192.168.1.200:2000`). Bus AUX **19200 baud 8N2, DATA single-wire half-duplex** (TX/RX sur un seul fil), driver en mode AUX direct (le driver gère le protocole binaire `0x3b…`, pas de pass-through `'P'`). Détails et brochage : [`docs/technical/hardware.md`](docs/technical/hardware.md). Pivot ESP32 : [ADR 2026-07-05](docs/project/decisions.md).
- **Capteurs** : DroTek Ublox M8N (UART0 GPIO), compass LIS3MDL à `0x1E` (I2C1). Pas d'USB pour les capteurs (réservés caméras). Détails : [`docs/technical/hardware.md`](docs/technical/hardware.md).
- **Plate Solving** (Macro 5+) : Astrometry.net local

## Architecture

```
App Flutter (téléphone) --[Wi-Fi / REST + SSE]--> FastAPI (Pi) --[WiFi/TCP → pont ESP32]--> bus AUX → Monture
                                                       │ UART0 + I2C1 GPIO
                                                       ▼
                                           DroTek GPS + LIS3MDL
```

- Pont ESP32 sur le bus AUX (interface WiFi + électrique, pas de temps-réel moteur) — déroge à l'ADR original « pas d'Arduino » (cf. ADR 2026-07-05)
- REST pour les commandes, SSE pour l'état — pas de WebSocket
- Pi gère la sync GPS → monture automatiquement au boot
- Détails : [`docs/technical/architecture.md`](docs/technical/architecture.md)

## Accès Pi

- Hostname : `astro-brain` (mDNS `astro-brain.local`)
- User : `pascal3100`
- SSH configuré avec clé (`~/.ssh/config`)

## Structure du repo

Monorepo à `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/` :

- `backend/` — package Python FastAPI (pyproject.toml + uv.lock à ce niveau)
- `app/` — app Flutter (`flutter_bloc`, design system dans `lib/theme/`)
- `docs/` — `INDEX.md` + 3 vues (`technical/`, `project/`, `product/`) + `superpowers/{specs,plans}/`
- `CLAUDE.md`, `README.md` — racine

## Workflow de dev

Hybride : édition côté workstation, exécution côté Pi.

- **Tooling Python** : `uv` (Python 3.13, venv, lockfile). Depuis `backend/` : `uv sync`, `uv run pytest`, `uv run uvicorn astro_brain.main:app --reload`.
- **Workstation** : édition + tests unitaires pur-logique avec fakes. Deps hardware exclues par défaut.
- **Pi** : clone à `~/code/astro-brain/`, `uv sync --extra hardware`, puis `git pull && systemctl restart astro-brain.service`.
- **Git = source de vérité** : rien de sensible hors du repo ; pas de sync manuelle workstation ↔ Pi.
- **App Flutter** : depuis `app/`, `flutter analyze` + `flutter test`. Validation visuelle sur Android physique en USB (pas Chrome / pas émulateur).

## Roadmap

Pas de versions numérotées. **Train d'étapes atomiques regroupées en macro-étapes** thématiques. Une étape se déplace dans le train ; une macro est "done" quand le télescope reste utilisable end-to-end à la fin (la discipline "livrable utilisable" vit au niveau macro). Voir ADR du 2026-05-05.

- **Macro 0 — Socle** ✅ (livré 2026-04-25) : joystick + tracking + GPS/heure auto, app Flutter native, AppBar template, service systemd
- **Macro 1 — Migration INDI** ✅ (bouclée 2026-07-05) : refonte `MountAdapter` `nexstarpy` → `pyindi-client`, monture pilotée via pont ESP32 (WiFi ↔ bus AUX)
- **Macro 2 — Setup** ✅ (done 2026-07-08) : page Setup unifiée + calibration compass, network/IP, à propos (niveau monture, calibration ADXL345 ×2 et courses ALT retirés le 2026-07-17 — voir ADR ; backlash mount-side reporté Macro 5)
- **Macro 3 — Mise en station + GoTo basique** : Hub central, wizard alignement 3 étoiles, GoTo réel, catalogue minimal (Messier + planètes + ~50-100 étoiles)
- **Macro 4 — Catalogue intelligent** : NGC/IC + setup tube + filtrage par caractéristiques tube — **parité raquette Celestron atteinte**
- **Macro 5 — Caméras + plate solving** : stack INDI caméras, pipeline preview FITS→JPEG, framing, machine d'état backend, Astrometry.net local
- **Macro 6 — Focus + MES complète** : focus live HFR/FWHM, wizard MES end-to-end, alignement par plate solve, assistant alignement optique
- **Macro 7 — Astrophoto** : PHD2 guidage, séquenceur, dithering, autofocus

Fils transverses (en continu, pas dans le train) : safety (urgence + logs), mode nuit, indicateur global, ops (deploy, build APK), night planner offline.

Roadmap détaillée et statut par étape : [`docs/project/roadmap.md`](docs/project/roadmap.md). ADRs : [`docs/project/decisions.md`](docs/project/decisions.md).

**À tenir à jour** : `docs/project/roadmap.md` est l'unique source de vérité du train. À chaque livraison d'étape (statut + date), à chaque réorganisation (déplacement / ajout / retrait d'étape entre macros), mettre à jour la roadmap **dans la même session que le commit qui livre le changement**. Les changements structurants (ajout/retrait de macro, déplacement entre macros) déclenchent aussi un ADR daté dans `decisions.md`.

## Conventions

- **Journal** : [`docs/project/journal.md`](docs/project/journal.md) — fil rouge du projet, à tenir à jour **pendant la session** (décisions, commits importants, blocages). **Plafond : 5-6 sessions max** ; au-delà, on archive par milestone dans `docs/project/journal/archive/<AAAA-MM-milestone>.md`.
- **Backlog** : [`docs/project/backlog.md`](docs/project/backlog.md) — réflexions prospectives transverses à arbitrer plus tard. Pas de réflexions prospectives dans le journal.
- **ADRs** : [`docs/project/decisions.md`](docs/project/decisions.md) — toute décision structurante (titre + contexte + choix + rationale).
- **Docs courts et ciblés** : 1 sujet = 1 fichier, navigation par liens. Quand on touche un sujet, mettre à jour le doc correspondant.
- **Specs de design** : `docs/superpowers/specs/`. **Plans d'implémentation** : `docs/superpowers/plans/`.
- **Design UI** : Material Design 3, style HUD spatial, double thème bleu (jour) / rouge (nuit). AppBar partagée sur tous les écrans (pastille `overall` + toggle thème + reconnect conditionnel). Détails : [`docs/product/design-system.md`](docs/product/design-system.md).
