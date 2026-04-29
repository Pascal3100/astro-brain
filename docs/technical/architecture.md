# Architecture globale

## Vue d'ensemble

```
App Flutter (téléphone)  ─[Wi-Fi / REST + SSE]─▶  FastAPI (Pi)  ─[USB-série]─▶  Monture Celestron
                                                       │ UART GPIO + I2C1
                                                       ▼
                                                 GPS DroTek + LIS3MDL + ADXL345
```

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+. Pas d'Arduino dans la chaîne.
- **Frontend** : app Flutter native (pas une PWA), pattern BLoC.
- **Communication Pi ↔ Monture** : `nexstarpy` via USB-série (port HC, protocole NexStar, 9600 baud).
- **Plate solving (v0.5+)** : Astrometry.net local sur le Pi.

## Décisions structurantes

- **REST + SSE, pas de WebSocket** — REST pour les commandes (`/slew`, `/stop`, `/tracking`, `/goto`), SSE pour le flux d'état (`/events`).
- **Source de vérité côté Pi** — GPS, heure, capteurs, état monture, calculs astro (skyfield/astropy). L'app est un client de présentation.
- **Catalogue côté backend** (à partir de v0.3) — endpoints REST exposent Messier, planètes, étoiles brillantes. Calculs Alt/Az faits en Python.
- **App offline-friendly seulement quand sans Pi pas de sens** — le night planner (post-v0.3) utilisera un pattern snapshot/cache, mais le contrôle direct exige le Pi allumé.

## Stack technique

- Python 3.13, gestion des deps avec `uv` (lockfile par projet)
- FastAPI + Uvicorn, SSE via `sse-starlette`
- `nexstarpy` (monture), `gpsd-py3` (GPS), `smbus2` (I2C compass + accelerometers)
- Flutter 3.41+ / Dart 3.11+, `flutter_bloc`, `equatable`, `google_fonts`, `phosphor_flutter`, `shared_preferences`
- Style UI : Material Design 3, thème bleu (jour) / rouge (nuit)

## Workflow de dev

Hybride : édition côté workstation, exécution côté Pi.

- **Workstation** : tests unitaires pur-logique (StateBus, aggregator, modèles, SSE format) avec fakes. Deps hardware exclues par défaut.
- **Pi** : `uv sync --extra hardware` pour `nexstarpy`/`gpsd-py3`/`pyserial`/`smbus2`, puis `git pull && uv run uvicorn ...` pour tester avec le matériel.
- **Git = source de vérité** — pas de sync manuelle workstation ↔ Pi.

Voir [deployment.md](deployment.md) pour les détails d'installation et le service systemd.
