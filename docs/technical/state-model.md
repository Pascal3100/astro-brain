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
| `tracking` | `MountService` | `off / sidereal / lunar / solar / error` | — |
| `network` | `NetworkInfoService` | `unknown / client / hotspot / offline / error` | `ssid, ip, iface, mode` |
| `system` | `SystemInfoService` | `unknown / ok / warn / error` | `cpu_temp, load_avg, uptime, clock_synced` |

> **Le bus santé porte 4 sous-systèmes** — `mount`, `tracking`, `network`, `system` — plus `alignment` (ci-dessous).
>
> Ce qui n'y est **pas**, et pourquoi :
>
> - **`gps` et `compass` n'existent plus.** Le module DroTek est retiré ([ADR 2026-08-26](../project/decisions.md)) : le Pi ne mesure plus ni position ni cap. La position vient du **site d'observation** persisté, écrit par l'app (`PUT /site`) — un état de configuration, pas un état de santé, donc hors bus. Lu/écrit à la demande via REST.
> - **L'horloge n'a pas son propre sous-système** : un booléen ne justifie pas un `SubsystemKind`. La synchro NTP sort dans `system.details.clock_synced` — et c'est elle qui autorise ou non la poussée d'heure vers la monture (sans synchro, `fake-hwclock` restitue l'heure du dernier arrêt).
> - Les **courses ALT** (`mount_limits`) ont été retirées le 2026-07-17 avec la feature Courses ALT, voir [ADR](../project/decisions.md).
>
> Voir [architecture.md](architecture.md#état-persistant--statedb).

## Sous-systèmes Macro 3 — Mise en station + GoTo (software livré)

| Kind | Service | États | Détails clés |
|---|---|---|---|
| `alignment` | `AlignmentService` | `idle / active` | `is_aligned, session_id, current_idx, recorded_count, candidate_ids` |

> **Contrat de bus courant.** Le wizard ne publie que deux états — `idle` (aucune session) et `active` (session en cours) — via `_publish_session` (routes/alignment.py), avec `is_aligned` toujours présent. La taxonomie fine envisagée initialement (`not_aligned / aligned / error` + `residual_deg`, `stars_synced`) n'est **pas** portée sur le bus : l'issue du solver revient dans la réponse REST `finalize` (`AlignmentModel`), pas dans le flux santé.

## Règles d'agrégation `overall`

Couleurs : `green / blue / orange / red / offline`.

L'agrégateur **dérive ses règles des enums** (FATAL / TRANSIENT / DEGRADED) — un rename d'état dans un service casse l'import au lieu de classer silencieusement mal.

### Macro 0 — Socle

- `mount=disconnected|error` → `red` (`mount` est le seul sous-système *critique*)
- `mount=connecting` → `blue` (transitionnel)
- `network=offline`, `system=warning|critical` → `orange` (degraded)
- Tout vert → `green`

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
