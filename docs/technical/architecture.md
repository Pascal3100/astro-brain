# Architecture globale

## Vue d'ensemble

```
App Flutter (téléphone)  ─[Wi-Fi / REST + SSE]─▶  FastAPI (Pi)  ─[pyindi-client]─▶  indiserver
                                                       │                               │ indi_celestron_aux (mode Serial)
                                                       │                               ▼
                                                       │                    /dev/ttyAMA0 (3 fils) ─▶ pont ESP32
                                                       │                                           │ RX LM2902 / TX 74AHCT125
                                                       │                                           ▼
                                                       │                                  bus AUX (HC RJ12) ─▶ Monture Celestron
                                                       ▼
                                              aiosqlite ─▶ /var/lib/astro-brain/state.db
                                                (site d'observation, alignement)
```

- **Backend** : FastAPI (Python 3.13) sur Raspberry Pi 3 B+.
- **Frontend** : app Flutter native (pas une PWA), pattern BLoC.
- **Communication Pi ↔ Monture** : stack INDI — `indiserver` + driver `indi_celestron_aux` côté Pi, client Python `pyindi-client` dans le backend FastAPI. Liaison physique : port HAND CONTROL (RJ-12) sur le **bus AUX** single-wire half-duplex (19200 8N2) → interface RX LM2902 / TX 74AHCT125 → **pont ESP32** relayant le bus vers le Pi sur une **liaison série 3 fils** (UART0, `/dev/ttyAMA0`), driver en **mode Serial**. Détails : [`indi-reference.md`](indi-reference.md) + [`hardware.md`](hardware.md). ADRs : [2026-05-01 — INDI (drop nexstarpy)](../project/decisions.md) + [2026-07-05 — pont ESP32](../project/decisions.md) + [2026-08-26 — pont filaire](../project/decisions.md).
- **Plate solving (Macro 5+)** : Astrometry.net local sur le Pi.

## Décisions structurantes

- **REST + SSE, pas de WebSocket** — REST pour les commandes (`/slew`, `/stop`, `/tracking`, `/goto`), SSE pour le flux d'état (`/events`).
- **Source de vérité côté Pi** — site d'observation persisté, heure NTP, état monture, calculs astro (skyfield/astropy). L'app est un client de présentation. Le Pi n'a **plus de capteur embarqué** depuis le retrait du module DroTek ([ADR 2026-08-26](../project/decisions.md)) : la position lui est **écrite** par l'app (`PUT /site`, depuis le GPS du téléphone), elle n'est pas mesurée localement.
- **Catalogue : source unique `reference.sqlite` (almanach Oracle), lue des deux côtés** — le Pi en tient sa copie (SP2) pour résoudre les GoTo par `id` ; **depuis Oracle SP3-B, l'app lit le catalogue et calcule la visibilité (alt/az) localement** depuis son propre cache `reference.sqlite` (téléchargé de la release GitHub `almanac-latest`), donc **catalogue navigable Pi éteint**. Le Pi ne sert plus le catalogue à l'app : **SP3-B bis (2026-08-11) a retiré `GET /catalog/objects`** et la couche liste/visibilité côté Pi (`VisibilityEnricher`, `list_all`/`list_objects`, `CatalogFilter`). **GoTo reste en ligne** : l'app envoie `{id, confirm_solar}`, le Pi le résout par `id` (`get_by_qualified_id`) et pointe.
- **App offline-first pour le catalogue Oracle** — navigation + visibilité fonctionnent Pi éteint (cache local `reference.sqlite`, sync online-first non bloquante au boot). Le **contrôle direct** (slew/goto/tracking) et l'état live exigent toujours le Pi allumé.

## Stack technique

- Python 3.13, gestion des deps avec `uv` (lockfile par projet)
- FastAPI + Uvicorn, SSE via `sse-starlette`
- `pyindi-client` (monture, via `indiserver` local) — seule dépendance hardware restante
- `aiosqlite` + `numpy` (base d'état persistante, algèbre de l'alignement 3 étoiles)
- Flutter 3.41+ / Dart 3.11+, `flutter_bloc`, `equatable`, `google_fonts`, `phosphor_flutter`, `shared_preferences`
- Style UI : Material Design 3, thème bleu (jour) / rouge (nuit)

## Processus sur le Pi

Deux processus cohabitent sur le Pi :

| Processus | Rôle | Systemd |
|-----------|------|---------|
| `astro-brain.service` | Backend FastAPI | `Requires=indiserver.service` |
| `indiserver` | Broker INDI + driver `indi_celestron_aux` | `indiserver.service` (démarré avant FastAPI) |

Le service FastAPI déclare `Requires=indiserver.service` pour garantir que le broker INDI est actif avant la tentative de connexion `pyindi-client`.

## État persistant — `state.db`

Le backend persiste son état durable dans une base SQLite locale (`aiosqlite`) : site d'observation et modèle d'alignement.

- Chemin : `/var/lib/astro-brain/state.db` (override via `ASTRO_BRAIN_STATE_DIR`).
- Géré par `astro-brain.service` via `StateDirectory=astro-brain` (création + permissions automatiques).
- Schéma initial : 3 tables (`schema_version`, `calibration_sensor`, `mount_limits`) — voir migration `_001_initial.py`. La table `mount_limits` est **inutilisée depuis le retrait de la feature Courses ALT** (2026-07-17, voir [ADR](../project/decisions.md)) ; conservée telle quelle (pas de migration de suppression). `calibration_sensor` a en revanche été **droppée** par `_008` avec le retrait du module DroTek : plus aucun capteur à calibrer. Migrations **forward-only** — les migrations appliquées ne sont jamais rééditées.
- La connexion vit sur `app.state.db`, ouverte au startup du lifespan FastAPI (migrations appliquées avant le démarrage des services), fermée au shutdown.
- **Site d'observation hors bus santé.** Lecture/écriture à la demande via REST (`GET`/`PUT /site`) ; une copie en mémoire alimente la chaîne de position du wizard d'alignement, semée au boot depuis la base.

## Workflow de dev

Hybride : édition côté workstation, exécution côté Pi.

- **Workstation** : tests unitaires pur-logique (StateBus, aggregator, modèles, SSE format) avec fakes. Deps hardware exclues par défaut.
- **Pi** : `uv sync --extra hardware` pour `pyindi-client`, plus packages apt INDI (`indi-bin`, `indi-celestronaux`, `libindi-dev` — repo Astroberry Trixie arm64). `indiserver` lancé via unit systemd dédiée, FastAPI s'y connecte sur `localhost:7624`. Cycle dev : `git pull && uv run uvicorn ...`.
- **Git = source de vérité** — pas de sync manuelle workstation ↔ Pi.

Voir [deployment.md](deployment.md) pour les détails d'installation et le service systemd.
