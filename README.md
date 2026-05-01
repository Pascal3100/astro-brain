# Astro-Brain

Système de contrôle autonome pour télescope DIY — backend FastAPI sur Raspberry Pi + app Flutter sur téléphone.

Pilote un Maksutov Bresser 127/1900 sur monture Celestron, dialogue avec la monture en USB-série (protocole NexStar) et lit le GPS depuis un module DroTek.

## Structure

- `backend/` — backend Python/FastAPI qui tourne sur le Raspberry Pi. Expose des commandes REST (`/slew`, `/stop`, `/tracking`) et un flux SSE d'état (`/events`).
- `app/` — application Flutter installée sur un téléphone. Joystick, diagnostics système, et (v0.3+) planificateur d'observation.
- `docs/` — documentation du projet, point d'entrée [`docs/INDEX.md`](docs/INDEX.md).

## Documentation

Trois angles de lecture, voir [`docs/INDEX.md`](docs/INDEX.md) :
- **[Technique](docs/technical/README.md)** — architecture, hardware, modèle d'état, API, déploiement.
- **[Projet](docs/project/README.md)** — roadmap, journal de sessions, backlog, ADRs.
- **[Produit](docs/product/README.md)** — features, parcours, design system.

Specs et plans : `docs/superpowers/specs/` et `docs/superpowers/plans/`. Journal en cours : [`docs/project/journal.md`](docs/project/journal.md).

## Roadmap

- **v0.1** ✓ Joystick + tracking + GPS/heure (livré 2026-04-25)
- **v0.2** Setup : calibration compass + ADXL345 ×2, courses ALT, backlash, cordwrap, network/IP, à propos
- **v0.3** Mise en station 3 étoiles + GoTo + catalogue minimal + Hub central
- **v0.4** Catalogue complet (NGC/IC) + filtrage par tube — parité raquette Celestron atteinte
- **v0.5** Caméras + plate solving (stack INDI, pipeline preview, framing)
- **v0.6** Focus + mise en station complète
- **v0.7** Astrophoto (PHD2 guidage, séquenceur, dithering, autofocus)

Détail : [`docs/project/roadmap.md`](docs/project/roadmap.md).
