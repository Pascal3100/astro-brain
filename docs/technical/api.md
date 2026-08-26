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

### Site d'observation (livré)

Seule source de position du backend depuis le retrait du module DroTek
([ADR 2026-08-26](../project/decisions.md)). Persisté en base
(`observing_site`, singleton), semé au boot, réécrit à chaud.

```
GET /site                    # 200 { lat, lon, set_at } | 200 null (jamais réglé)
PUT /site  { lat, lon }      # 204 — persiste + applique à chaud (422 hors bornes)
```

`GET` renvoie le littéral `null` plutôt qu'un `404` : l'absence de site est un
état nominal (première installation), pas une erreur. `PUT` met aussi à jour le
provider de position en mémoire, pour que `/align/start` débloque sans
redémarrage. Bornes : `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`.

Le site n'est écrit que sur **action explicite** de l'utilisateur (bouton
« Utiliser la position du téléphone » dans Setup) — jamais automatiquement au
lancement de l'app : la garde ΔGPS 20 m de l'alignement comparerait sinon le
modèle persisté à un GPS téléphone qui gigue, et invaliderait un alignement
encore valide.

_(Les endpoints `/calibration/*` et `/sensors/compass/stream` ont été retirés
le 2026-08-26 avec le module DroTek — voir [ADR](../project/decisions.md).)_

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
data: { "subsystems": { "mount": {...}, "tracking": {...}, "network": {...}, "system": {...} }, "overall": "green" }

event: state
data: { "subsystem": "mount", "state": {...} }
```

Reconnexion : SSE relance auto avec backoff exp `[1s, 2s, 4s, 10s]` côté client. À la reconnexion, le serveur envoie un `snapshot` complet pour resynchroniser.

## Erreurs

- `409 Conflict` : précondition non remplie (ex: `/goto` sans alignement). Message explicite dans le body.
- `503 Service Unavailable` : sous-système hardware en `error` (monture déconnectée). Message + `subsystem` dans le body.
- `400 Bad Request` : payload invalide (RA/Dec hors plage, valeurs incohérentes).
