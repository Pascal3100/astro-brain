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
| `tilt` | `TiltService` (ADXL345 monture `0x1D`) | `unknown / level / off_level / error` | `pitch_deg, roll_deg, magnitude_deg` |
| `compass` | `CompassService` (LIS3MDL `0x1E`) | `unknown / ok / needs_calibration / error` | `heading_deg, magnitude_uT` |

> **Calibration et limits hors bus.** Les payloads de calibration capteurs (`calibration_sensor`) et les courses ALT (`mount_limits`) **ne sont pas publiés sur le bus santé** en Macro 2. Ils sont persistés dans `state.db` (aiosqlite) et lus à la demande via REST. Le bus santé reste donc sur ses 5 sous-systèmes initiaux (`mount`, `gps`, `tracking`, `network`, `system`), plus `tilt`/`compass` quand les services seront livrés. Voir [architecture.md](architecture.md#état-persistant--statedb).

## Sous-systèmes prévus Macro 3 — Mise en station + GoTo basique

| Kind | Service | États | Détails clés |
|---|---|---|---|
| `alignment` | `AlignmentService` | `not_aligned / wizard_in_progress / aligned / error` | `step (1..6), residual_deg, stars_synced (0..3)` |

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
- `tilt=error` ou `compass=error` → `orange` (capteur capricieux, app reste utilisable)
- `tilt=off_level` → neutre (info pendant wizard, pas une erreur globale)

### Extensions Macro 3 — Mise en station + GoTo basique

- `alignment=error` → `blue` (correctable user, pas une panne hardware)
- `alignment=not_aligned` → neutre
- `alignment=wizard_in_progress` → `blue` (en cours)

## Format SSE

Le flux `/events` envoie deux types de messages :

- `event: state` — patch incrémental d'un sous-système
- `event: snapshot` — état complet (envoyé à la connexion + sur reconnexion)

Voir [api.md](api.md) pour les détails du format JSON.

## Tests

Tests unitaires côté workstation : `StateBus`, agrégateur (transitions FATAL/TRANSIENT/DEGRADED), modèles Pydantic, format SSE. Hardware mocké via fakes.
