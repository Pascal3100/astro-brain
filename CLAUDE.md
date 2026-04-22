# Astro-Brain DIY

## Description du projet

Système de contrôle autonome pour télescope Maksutov Bresser 127/1900 sur monture Celestron. Le Raspberry Pi communique directement avec la monture (pas d'Arduino) et sert de backend pour une app Flutter sur téléphone.

## Documentation

- Architecture hardware initiale : `docs/architecture_hardware.txt`
- Spec design v0.1 : `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md`
- Backlog réflexions post-v0.1 : `docs/backlog.md` (idées transverses à arbitrer plus tard)

## Stack technique

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+
- **Frontend** : App Flutter native sur téléphone (pas une PWA)
- **Communication Pi <-> Monture** : nexstarpy via USB-série (port HC, protocole NexStar, 9600 baud)
- **GPS** : Module DroTek Ublox M8N + compass magnétique (UART GPIO sur Pi, USB réservé aux caméras — voir `docs/hardware_wiring.md`)
- **Plate Solving** (v0.2+) : Astrometry.net (local)

## Architecture

```
App Flutter (téléphone) --[Wi-Fi / REST]--> FastAPI (Pi) --[USB-série]--> Monture Celestron
                                                 │ UART GPIO (+ I2C pour compass)
                                                 ▼
                                           DroTek GPS + compass
```

- Pas d'Arduino dans la chaîne
- REST pour les commandes (`/slew`, `/stop`, `/tracking`), SSE pour le flux d'état (`/events`) — pas de WebSocket en v0.1
- Le Pi gère la sync GPS → monture automatiquement au boot

## Accès Pi

- Hostname : `astro-brain` (résolvable aussi via mDNS en `astro-brain.local` depuis l'install d'avahi-daemon)
- User : `pascal3100`
- SSH configuré avec clé (`~/.ssh/config`)

## Structure du repo

Monorepo à `/home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/` :

- `backend/` — package Python FastAPI (pyproject.toml + uv.lock au niveau de ce dossier)
- `app/` — app Flutter (à créer dans un plan dédié)
- `docs/` — specs (`docs/superpowers/specs/`), plans (`docs/superpowers/plans/`), journal, archi hardware
- `CLAUDE.md`, `README.md` — racine

## Workflow de dev

Hybride : édition côté workstation, exécution côté Pi.

- **Tooling Python** : `uv` (Python 3.13, venv, lockfile). Commandes clés depuis `backend/` : `uv sync`, `uv run pytest`, `uv run uvicorn astro_brain.main:app --reload`.
- **Workstation** : édition + tests unitaires pur-logique (StateBus, aggregator, modèles Pydantic, SSE format) avec fakes — pas de hardware nécessaire. Deps hardware exclues par défaut.
- **Pi** : clone à `~/code/astro-brain/`, `uv sync --extra hardware` pour installer `nexstarpy`/`gpsd-py3`/`pyserial`, puis `git pull && uv run uvicorn ...` pour tester avec le vrai matériel.
- **Git = source de vérité** : rien de sensible hors du repo ; pas de sync manuelle workstation ↔ Pi.

## Roadmap

Philosophie : **chaque version = un livrable utilisable en session réelle**. On vise d'abord la parité avec la raquette Celestron (v0.1 → v0.3, sans caméra), puis on greffe la chaîne caméra/plate solve/guidage par-dessus.

- **v0.1** : Joystick + tracking + GPS/heure
- **v0.2** : GoTo + alignement assisté 3 étoiles (exploite GPS + compass + niveau pour pré-pointer les étoiles de référence)
- **v0.3** : Catalogue intelligent + page "setup tube" (filtrage des objets selon focale/diamètre/obstruction du tube). **À ce stade, parité fonctionnelle avec la raquette Celestron.**
- **v0.4** : Fondations caméras + Plate solving (stack INDI, config caméras, pipeline preview FITS→JPEG, page framing, machine d'état backend idle/focus/guide/image)
- **v0.5** : Mise au point + Mise en station (page focus live + HFR/FWHM, wizard mise en station, réglages techniques monture comme courses ALT/AZ & backlash)
- **v0.6** : Astrophoto (intégration PHD2 guidage, séquenceur de poses, dithering, autofocus périodique)

## Conventions

- Le journal de session est dans `docs/journal.md` — **fil rouge du projet**, à tenir à jour **régulièrement pendant la session** (décisions d'archi, commits importants, blocages), pas uniquement à la fin
- **Structure du journal** : `docs/journal.md` reste compact (état projet + session en cours + index des archives). À chaque jalon significatif (plan achevé, version livrée), basculer la session courante dans `docs/journal/archive/AAAA-MM-<milestone>.md`, mettre à jour "État du projet", et repartir sur une session vide. Les archives sont consultables à la demande mais plus chargées par défaut.
- Les specs de design sont dans `docs/superpowers/specs/`
- Les plans d'implémentation sont dans `docs/superpowers/plans/`
- Design UI : style HUD spatial, Material Design 3, thème bleu (jour) / rouge (nuit)
