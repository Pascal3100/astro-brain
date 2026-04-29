# Astro-Brain DIY

## Description du projet

Système de contrôle autonome pour télescope Maksutov Bresser 127/1900 sur monture Celestron. Le Raspberry Pi communique directement avec la monture (pas d'Arduino) et sert de backend pour une app Flutter sur téléphone.

## Documentation

**Point d'entrée unique** : [`docs/INDEX.md`](docs/INDEX.md) — référence trois vues `technical/`, `project/`, `product/`.

- **Technique** ([`docs/technical/`](docs/technical/README.md)) : architecture, hardware/wiring, modèle d'état, API, déploiement.
- **Projet** ([`docs/project/`](docs/project/README.md)) : roadmap, ADRs (`decisions.md`), journal (`journal.md`), backlog (`backlog.md`).
- **Produit** ([`docs/product/`](docs/product/README.md)) : design system, fiches features.

Specs et plans : `docs/superpowers/specs/` et `docs/superpowers/plans/`.

## Stack technique

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+
- **Frontend** : App Flutter native sur téléphone (pas une PWA), pattern BLoC
- **Communication Pi <-> Monture** : `nexstarpy` via USB-série (port HC, protocole NexStar, 9600 baud)
- **Capteurs** : DroTek Ublox M8N (UART0 GPIO), compass LIS3MDL à `0x1E` (I2C1), 2× ADXL345 à `0x53`/`0x1D` (I2C1). Pas d'USB pour les capteurs (réservés caméras). Détails : [`docs/technical/hardware.md`](docs/technical/hardware.md).
- **Plate Solving** (v0.5+) : Astrometry.net local

## Architecture

```
App Flutter (téléphone) --[Wi-Fi / REST + SSE]--> FastAPI (Pi) --[USB-série]--> Monture Celestron
                                                       │ UART0 + I2C1 GPIO
                                                       ▼
                                           DroTek GPS + LIS3MDL + 2× ADXL345
```

- Pas d'Arduino dans la chaîne
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

Philosophie : **chaque version = un livrable utilisable en session réelle**. On vise d'abord la parité avec la raquette Celestron (v0.1 → v0.4, sans caméra), puis on greffe la chaîne caméra/plate solve/guidage.

- **v0.1** ✓ Joystick + tracking + GPS/heure (livré 2026-04-25)
- **v0.2** Setup : calibration compass + ADXL345 ×2, courses ALT/AZ, backlash, network/IP, à propos
- **v0.3** Mise en station 3 étoiles + GoTo + catalogue minimal (Messier + planètes + ~50-100 étoiles brillantes) + Hub central
- **v0.4** Catalogue complet (NGC/IC) + filtrage par tube (focale, diamètre, obstruction) — **parité raquette Celestron atteinte**
- **v0.5** Caméras + plate solving (stack INDI, pipeline preview FITS→JPEG, framing)
- **v0.6** Focus + mise en station complète (focus live HFR/FWHM, wizard avec option plate solve)
- **v0.7** Astrophoto (PHD2 guidage, séquenceur, dithering, autofocus)

Roadmap détaillée : [`docs/project/roadmap.md`](docs/project/roadmap.md). ADRs : [`docs/project/decisions.md`](docs/project/decisions.md).

## Conventions

- **Journal** : [`docs/project/journal.md`](docs/project/journal.md) — fil rouge du projet, à tenir à jour **pendant la session** (décisions, commits importants, blocages). **Plafond : 5-6 sessions max** ; au-delà, on archive par milestone dans `docs/project/journal/archive/<AAAA-MM-milestone>.md`.
- **Backlog** : [`docs/project/backlog.md`](docs/project/backlog.md) — réflexions prospectives transverses à arbitrer plus tard. Pas de réflexions prospectives dans le journal.
- **ADRs** : [`docs/project/decisions.md`](docs/project/decisions.md) — toute décision structurante (titre + contexte + choix + rationale).
- **Docs courts et ciblés** : 1 sujet = 1 fichier, navigation par liens. Quand on touche un sujet, mettre à jour le doc correspondant.
- **Specs de design** : `docs/superpowers/specs/`. **Plans d'implémentation** : `docs/superpowers/plans/`.
- **Design UI** : Material Design 3, style HUD spatial, double thème bleu (jour) / rouge (nuit). AppBar partagée sur tous les écrans (pastille `overall` + toggle thème + reconnect conditionnel). Détails : [`docs/product/design-system.md`](docs/product/design-system.md).
