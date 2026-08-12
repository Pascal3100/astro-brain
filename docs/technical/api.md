# API REST + SSE

Document vivant. Liste les endpoints par macro-étape. Les ajouts d'endpoints sont mineurs ; les ruptures de contrat sont notées explicitement.

Convention : RA/Dec en **degrés décimaux** dans toutes les requêtes/réponses (jamais en h:m:s).

## Macro 0 — Socle (livré)

### Commandes monture

```
POST /slew     { axis: "alt" | "az", direction: "+" | "-", rate: 1..8 }   # 8x max (driver INDI, cf. S38)
POST /stop     { axis?: "alt" | "az" }           # omettre axis = stoppe tout slew actif
POST /tracking { enabled: bool }                 # suivi sidéral on/off
POST /mount/reconnect                            # reconnect monture (non bloquant, progrès via SSE)
GET  /state                                      # snapshot complet du SystemState
```

### Flux d'état

```
GET /events                           # SSE — event: state | snapshot
```

## Macro 2 — Setup ✅ (done 2026-07-08)

Détails dans la spec Setup : [`docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md`](../superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md).

### Calibration capteurs (livré)

`sensor_id ∈ { lis3mdl }`. Une seule session active à la fois (verrou backend) ; conflit → `409`.

```
POST /calibration/{sensor_id}/start          # 202 { session_id } | 503 capteur muet
GET  /calibration/{sensor_id}/stream         # SSE — event: progress | end
POST /calibration/{sensor_id}/finalize       # 200 CalibrationStatus (persisté state.db)
POST /calibration/{sensor_id}/abort          # 200 { ok: true }
GET  /calibration/{sensor_id}                # 200 CalibrationStatus | 404 (jamais calibré)
```

Payloads par capteur :
- `lis3mdl` : `{ offsets: [x,y,z], scale_matrix: [[…]×3], coverage_pct: float, residual: float }`

Stream `progress` : `{ state: "sampling"|"computing", samples_n, coverage_pct, sigma, hint? }`. `end` : payload `CalibrationStatus` (succès) ou `{ error }` (échec).

### Streams capteurs live (livré)

```
GET /sensors/compass/stream?hz=5             # SSE CompassReading { heading_deg, tilt_compensated, magnitude_uT }
```

`hz` ∈ [1, 10]. Hors borne → `422`. Streams lazy : aucun I2C lu tant qu'aucun client connecté.

**Capteur absent** (puce non alimentée ou débranchée — l'état nominal du bench) :
le LIS3MDL fait lever `OSError` à smbus2, traduit en `SensorUnavailableError` et
rendu en **`503`**. Le capteur est acquis *avant* que la réponse SSE ne soit
rendue, sinon l'échec arriverait après les en-têtes et le client recevrait un
corps chunké tronqué au lieu d'un statut. Une puce perdue *en cours* de flux
émet un événement `error` (`{ detail }`) puis ferme le flux.

### À propos (livré)

```
GET  /about                  # 200 versions, IP/SSID, uptime, started_at
```

_(Les endpoints Courses ALT `GET`/`PUT /limits/alt` ont été retirés le 2026-07-17 avec la feature Courses ALT — voir [ADR](../project/decisions.md).)_

### Backlash mount-side — reporté Macro 5

Adapter backend `get/set_backlash` déjà écrit (vecteur INDI `MOUNT_AXIS_BACKLASH`) mais **aucune route REST** : le driver `indi_celestron_aux` v1.5 n'expose pas la propriété → nécessite un fork/patch C++, sans valeur avant l'imaging. Déplacé en Macro 5 ([ADR 2026-07-08](../project/decisions.md)).

## Macro 3 — Mise en station + GoTo (software livré, validation matérielle en cours)

### Wizard d'alignement 3 étoiles — préfixe `/align`

```
GET    /align/session                                     # { session: AlignmentSession | null }
POST   /align/location/client { lat, lon }                # position téléphone si pas de fix GPS Pi
POST   /align/start                                       # démarre le wizard (409 si position inconnue / conflit)
POST   /align/swap/{idx}      { star }                    # remplace l'étoile idx du triplet
POST   /align/record          { idx }                     # enregistre le sync sur l'étoile idx
POST   /align/restart_star    { idx }                     # recommence l'étoile idx
POST   /align/finalize                                    # → AlignmentModel
DELETE /align/session                                     # annule le wizard (204)
GET    /align/constellation/{abbr}?target_ra&target_dec   # figure constellation + étoile cible marquée
GET    /align/stars/visible                               # étoiles pointables groupées par constellation
```

Erreurs wizard : `ConflictError → 409`, `ValueError` du solver → `422`, position requise → `409`, constellation/abréviation inconnue → `404`.

### GoTo — résolution par `id`

```
POST /goto  { id, confirm_solar?: bool }        # précond: monture alignée ; abort via POST /stop
```

Gardes backend (toutes en `409` sauf id inconnu) : `reference_unavailable` (référence pas prête), `unknown_id` (**404**), `ephemeris_stale` (objet éphémère hors fenêtre), `not_aligned`, `goto_in_progress`, `solar_ack_required` (pointage Soleil sans `confirm_solar`).

## Référence / Oracle (SP2)

Catalogue unifié dans `reference.sqlite` (almanach Oracle — genèse : [`oracle-genese.md`](../project/oracle-genese.md)).

```
GET  /reference/status     # { ready, schema_version?, generated_at?, window_start?, window_end? }
POST /reference/sync       # { status, schema_version? } — refresh online-first non bloquant
```

> **Endpoints ops/diagnostic.** `GET /reference/status` et `POST /reference/sync` n'ont aucun consommateur app (l'app lit sa copie locale, cf. contrat ci-dessous) ; ils servent au re-sync manuel et au health probe du Pi (debug, scripts d'exploitation).

> **Contrat courant (Oracle SP2/SP3).** **GoTo passe par `id`** (le Pi résout contre sa copie de `reference.sqlite`), plus de RA/Dec brut côté route. **Depuis SP3-B, l'app ne consomme plus le catalogue via REST** — elle lit sa copie locale et calcule la visibilité côté téléphone ; seul GoTo reste un appel en ligne. **SP3-B bis (2026-08-11) : l'endpoint `GET /catalog/objects` a été retiré** (plus aucun consommateur) avec toute la couche liste/visibilité côté Pi (`VisibilityEnricher`, `ReferenceCatalog.list_all`, `list_objects`, `CatalogFilter`) ; le Pi ne garde que le chemin GoTo (`get_by_qualified_id` → `get_object`). Les endpoints hérités du plan initial (`/catalog/messier|planets|bright-stars|object/{id}/altaz`) n'ont jamais été implémentés sous ce contrat.

## Format SSE

```
event: snapshot
data: { "subsystems": { "mount": {...}, "gps": {...}, ... }, "overall": "green" }

event: state
data: { "subsystem": "gps", "state": {...} }
```

Reconnexion : SSE relance auto avec backoff exp `[1s, 2s, 4s, 10s]` côté client. À la reconnexion, le serveur envoie un `snapshot` complet pour resynchroniser.

## Erreurs

- `409 Conflict` : précondition non remplie (ex: `/goto` sans alignement). Message explicite dans le body.
- `503 Service Unavailable` : sous-système hardware en `error` (monture déconnectée, I2C fail). Message + `subsystem` dans le body.
- `400 Bad Request` : payload invalide (RA/Dec hors plage, valeurs incohérentes).
