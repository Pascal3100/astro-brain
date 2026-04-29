# API REST + SSE

Document vivant. Liste les endpoints par version. Les changements suivent un versioning sémantique informel — les ajouts d'endpoints sont mineurs, les ruptures de contrat sont notées explicitement.

Convention : RA/Dec en **degrés décimaux** dans toutes les requêtes/réponses (jamais en h:m:s).

## v0.1 (livré)

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

## v0.2 (Setup — à spécifier)

Détails dans la spec Setup à venir : `docs/superpowers/specs/<date>-astro-brain-v02-setup-design.md`.

Endpoints anticipés :

```
POST /compass/calibration/start
POST /compass/calibration/finish
POST /tilt/{tube|mount}/calibrate-zero
POST /mount/courses          { alt_min, alt_max, az_min, az_max }
POST /mount/backlash         { alt_steps, az_steps }
GET  /mount/courses
GET  /mount/backlash
```

## v0.3 (Alignement + GoTo — à spécifier)

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
