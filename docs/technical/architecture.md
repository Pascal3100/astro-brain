# Architecture globale

## Vue d'ensemble

```
App Flutter (téléphone)  ─[Wi-Fi / REST + SSE]─▶  FastAPI (Pi)  ─[pyindi-client]─▶  indiserver
                                                       │ UART GPIO + I2C1              │ indi_celestron_aux
                                                       │                               ▼
                                                       │                         /dev/ttyUSB0 (CP2102)
                                                       │                               │
                                                       │                            HC RJ12 ─▶ Monture Celestron
                                                       ▼
                                                 GPS DroTek + LIS3MDL + ADXL345
                                                       │
                                                       ▼
                                              aiosqlite ─▶ /var/lib/astro-brain/state.db
```

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+. Pas d'Arduino dans la chaîne.
- **Frontend** : app Flutter native (pas une PWA), pattern BLoC.
- **Communication Pi ↔ Monture** : stack INDI — `indiserver` + driver `indi_celestron_aux` côté Pi, client Python `pyindi-client` dans le backend FastAPI. Liaison physique : port HC RJ12 → dongle USB-TTL CP2102 (5V) → `/dev/ttyUSB0` (NexStar 9600 baud, AUX en pass-through). Détails : [`indi-reference.md`](indi-reference.md). ADR : [2026-05-01 — Pilotage monture via INDI (drop nexstarpy)](../project/decisions.md).
- **Plate solving (Macro 5+)** : Astrometry.net local sur le Pi.

## Décisions structurantes

- **REST + SSE, pas de WebSocket** — REST pour les commandes (`/slew`, `/stop`, `/tracking`, `/goto`), SSE pour le flux d'état (`/events`).
- **Source de vérité côté Pi** — GPS, heure, capteurs, état monture, calculs astro (skyfield/astropy). L'app est un client de présentation.
- **Catalogue côté backend** (à partir de Macro 3) — endpoints REST exposent Messier, planètes, étoiles brillantes. Calculs Alt/Az faits en Python.
- **App offline-friendly seulement quand sans Pi pas de sens** — le night planner (post-Macro 3) utilisera un pattern snapshot/cache, mais le contrôle direct exige le Pi allumé.

## Stack technique

- Python 3.13, gestion des deps avec `uv` (lockfile par projet)
- FastAPI + Uvicorn, SSE via `sse-starlette`
- `pyindi-client` (monture, via `indiserver` local), `gpsd-py3` (GPS), `smbus2` (I2C compass + accelerometers)
- `aiosqlite` + `numpy` (calibration capteurs Macro 2 — DB persistante hors bus santé, calculs bias/ellipsoid)
- Flutter 3.41+ / Dart 3.11+, `flutter_bloc`, `equatable`, `google_fonts`, `phosphor_flutter`, `shared_preferences`
- Style UI : Material Design 3, thème bleu (jour) / rouge (nuit)

## Processus sur le Pi

Trois processus cohabitent sur le Pi :

| Processus | Rôle | Systemd |
|-----------|------|---------|
| `astro-brain.service` | Backend FastAPI | `Requires=indiserver.service gpsd.service` |
| `indiserver` | Broker INDI + driver `indi_celestron_aux` | `indiserver.service` (démarré avant FastAPI) |
| `gpsd` | Démon GPS (UART0) | `gpsd.service` |

Le service FastAPI déclare `Requires=indiserver.service` pour garantir que le broker INDI est actif avant la tentative de connexion `pyindi-client`.

## État persistant — `state.db`

À partir de Macro 2, le backend persiste les calibrations capteurs et les courses ALT dans une base SQLite locale (`aiosqlite`).

- Chemin : `/var/lib/astro-brain/state.db` (override via `ASTRO_BRAIN_STATE_DIR`).
- Géré par `astro-brain.service` via `StateDirectory=astro-brain` (création + permissions automatiques).
- Schéma initial : 3 tables (`schema_version`, `calibration_sensor`, `mount_limits`) — voir migration `_001_initial.py`.
- La connexion vit sur `app.state.db`, ouverte au startup du lifespan FastAPI (migrations appliquées avant le démarrage des services), fermée au shutdown.
- **Calibration et limits ne sont pas sur le bus santé.** Lecture à la demande via REST (`GET /calibration/status`, `GET /limits/alt`).

## Workflow de dev

Hybride : édition côté workstation, exécution côté Pi.

- **Workstation** : tests unitaires pur-logique (StateBus, aggregator, modèles, SSE format) avec fakes. Deps hardware exclues par défaut.
- **Pi** : `uv sync --extra hardware` pour `pyindi-client`/`gpsd-py3`/`pyserial`/`smbus2`, plus packages apt INDI (`indi-bin`, `indi-celestronaux`, `indi-gpsd`, `libindi-dev` — repo Astroberry Trixie arm64). `indiserver` lancé via unit systemd dédiée, FastAPI s'y connecte sur `localhost:7624`. Cycle dev : `git pull && uv run uvicorn ...`.
- **Git = source de vérité** — pas de sync manuelle workstation ↔ Pi.

Voir [deployment.md](deployment.md) pour les détails d'installation et le service systemd.
