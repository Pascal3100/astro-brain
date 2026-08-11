# Modèle d'état (StateBus + agrégateur)

Document vivant. Liste les sous-systèmes, leurs états, et les règles d'agrégation `overall`.

## Bus interne (`StateBus`)

- Pattern pub/sub asynchrone, mono-process. Chaque service publie ses changements ; un agrégateur consomme tout pour calculer un état global.
- **Invariant** : `publish()` se fait uniquement sur la main-loop asyncio. Les adapters qui font de l'I/O bloquant via `asyncio.to_thread(...)` reprennent sur la main-loop avant de publier.
- Format publié : `Subsystem(kind, state, since, message?, details?)`.

## Sous-systèmes Macro 0 — Socle (livré)

| Kind | Service | États | Détails clés |
|---|---|---|---|
| `mount` | `MountService` (INDI) | `unknown / ready / moving / error / off` | `firmware_version` |
| `gps` | `GpsService` (gpsd) | `unknown / acquiring / fix_2d / fix_3d / off / error` | `lat, lon, alt, satellites, hdop, time_utc` |
| `tracking` | `MountService` | `off / sidereal / lunar / solar / error` | — |
| `network` | `NetworkInfoService` | `unknown / client / hotspot / offline / error` | `ssid, ip, iface, mode` |
| `system` | `SystemInfoService` | `unknown / ok / warn / error` | `cpu_temp, load_avg, uptime` |

## Sous-systèmes prévus Macro 2 — Setup

| Kind | Service | États | Détails clés |
|---|---|---|---|
| `compass` | `CompassService` (LIS3MDL `0x1E`) | `unknown / ok / needs_calibration / error` | `heading_deg, magnitude_uT` |

> **Calibration hors bus.** Les payloads de calibration capteurs (`calibration_sensor`) **ne sont pas publiés sur le bus santé** en Macro 2. Ils sont persistés dans `state.db` (aiosqlite) et lus à la demande via REST. Le bus santé reste donc sur ses 5 sous-systèmes initiaux (`mount`, `gps`, `tracking`, `network`, `system`), plus `compass` quand le service sera livré. (Les courses ALT — sous-système `mount_limits` — ont été retirées le 2026-07-17 avec la feature Courses ALT, voir [ADR](../project/decisions.md).) Voir [architecture.md](architecture.md#état-persistant--statedb).

## Sous-systèmes Macro 3 — Mise en station + GoTo (software livré)

| Kind | Service | États | Détails clés |
|---|---|---|---|
| `alignment` | `AlignmentService` | `idle / active` | `is_aligned, session_id, current_idx, recorded_count, candidate_ids` |

> **Contrat de bus courant.** Le wizard ne publie que deux états — `idle` (aucune session) et `active` (session en cours) — via `_publish_session` (routes/alignment.py), avec `is_aligned` toujours présent. La taxonomie fine envisagée initialement (`not_aligned / aligned / error` + `residual_deg`, `stars_synced`) n'est **pas** portée sur le bus : l'issue du solver revient dans la réponse REST `finalize` (`AlignmentModel`), pas dans le flux santé.

## Règles d'agrégation `overall`

Couleurs : `green / blue / orange / red / offline`.

L'agrégateur **dérive ses règles des enums** (FATAL / TRANSIENT / DEGRADED) — un rename d'état dans un service casse l'import au lieu de classer silencieusement mal.

### Macro 0 — Socle

- `mount=error` ou `system=error` → `red`
- `gps=acquiring`, `mount=moving`, `tracking=*` (transitionnel) → `blue`
- `gps=off`, `network=offline` → `orange` (degraded)
- Tout vert → `green`

### Extensions Macro 2 — Setup (à confirmer dans la spec Setup)

- `compass=needs_calibration` → `orange` (degraded — utilisable mais le wizard refuse de continuer)
- `compass=error` → `orange` (capteur capricieux, app reste utilisable)

### Extensions Macro 3 — Mise en station + GoTo

- `alignment=active` → `blue` (wizard en cours, transitionnel)
- `alignment=idle` → neutre

## Format SSE

Le flux `/events` envoie deux types de messages :

- `event: state` — patch incrémental d'un sous-système
- `event: snapshot` — état complet (envoyé à la connexion + sur reconnexion)

Voir [api.md](api.md) pour les détails du format JSON.

## Tests

Tests unitaires côté workstation : `StateBus`, agrégateur (transitions FATAL/TRANSIENT/DEGRADED), modèles Pydantic, format SSE. Hardware mocké via fakes.
