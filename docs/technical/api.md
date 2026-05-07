# API REST + SSE

Document vivant. Liste les endpoints par macro-étape. Les ajouts d'endpoints sont mineurs ; les ruptures de contrat sont notées explicitement.

Convention : RA/Dec en **degrés décimaux** dans toutes les requêtes/réponses (jamais en h:m:s).

## Macro 0 — Socle (livré)

### Commandes monture

```
POST /slew { axis: "alt" | "az", direction: "+" | "-", rate: 1..9 }
POST /stop { axis: "alt" | "az" | "all" }
POST /tracking { mode: "off" | "sidereal" | "lunar" | "solar" }
GET  /state                           # snapshot complet du SystemState
```

### Flux d'état

```
GET /events                           # SSE — event: state | snapshot
```

## Macro 2 — Setup (Slice A livré 2026-05-07)

Détails dans la spec Setup : [`docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md`](../superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md).

### Calibration capteurs (livré)

`sensor_id ∈ { adxl345_mount, adxl345_tube, lis3mdl }`. Une seule session active à la fois (verrou backend) ; conflit → `409`.

```
POST /calibration/{sensor_id}/start          # 202 { session_id }
GET  /calibration/{sensor_id}/stream         # SSE — event: progress | end
POST /calibration/{sensor_id}/finalize       # 200 CalibrationStatus (persisté state.db)
POST /calibration/{sensor_id}/abort          # 200 { ok: true }
GET  /calibration/{sensor_id}                # 200 CalibrationStatus | 404 (jamais calibré)
```

Payloads par capteur :
- `adxl345_*` : `{ bias: [x,y,z], sigma: float }`
- `lis3mdl` : `{ offsets: [x,y,z], scale_matrix: [[…]×3], coverage_pct: float, residual: float }`

Stream `progress` : `{ state: "sampling"|"computing", samples_n, coverage_pct, sigma, hint? }`. `end` : payload `CalibrationStatus` (succès) ou `{ error }` (échec).

### Streams capteurs live (livré)

```
GET /sensors/tilt/stream?hz=5                # SSE TiltReading { pitch_deg, roll_deg, magnitude_deg }
GET /sensors/compass/stream?hz=5             # SSE CompassReading { heading_deg, tilt_compensated, magnitude_uT }
```

`hz` ∈ [1, 20]. Hors borne → `422`. Streams lazy : aucun I2C lu tant qu'aucun client connecté.

### Endpoints anticipés (Slices B/C/D, non livrés)

```
POST /setup/limits/alt       { alt_min_deg, alt_max_deg }      # Slice B
GET  /setup/limits/alt
POST /mount/backlash         { az_pos, az_neg, alt_pos, alt_neg }  # Slice D — bloqué dongle
GET  /mount/backlash
POST /mount/cordwrap         { enabled, position_deg }              # Slice D
GET  /system/about                                                  # Slice C
POST /system/restart                                                # Slice C
```

## Macro 3 — Mise en station + GoTo basique (à spécifier)

```
POST /alignment/start
POST /alignment/advance
POST /alignment/sync-star    { ra_deg, dec_deg }
POST /alignment/finalize
POST /alignment/abort
POST /goto                   { ra_deg, dec_deg }    # précond: alignment=aligned
GET  /catalog/messier
GET  /catalog/planets
GET  /catalog/bright-stars
GET  /catalog/object/{id}/altaz
```

## Format SSE

```
event: snapshot
data: { "subsystems": { "mount": {...}, "gps": {...}, ... }, "overall": "green" }

event: state
data: { "subsystem": "gps", "state": {...} }
```

Reconnexion : SSE relance auto avec backoff exp `[1s, 2s, 4s, 10s]` côté client. À la reconnexion, le serveur envoie un `snapshot` complet pour resynchroniser.

## Erreurs

- `409 Conflict` : précondition non remplie (ex: `/goto` sans alignement, `/alignment/advance` sans tilt level). Message explicite dans le body.
- `503 Service Unavailable` : sous-système hardware en `error` (monture déconnectée, I2C fail). Message + `subsystem` dans le body.
- `400 Bad Request` : payload invalide (RA/Dec hors plage, valeurs incohérentes).
