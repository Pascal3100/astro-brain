# Design — Oracle SP2 : consommateur backend (Pi lit `reference.sqlite`)

Date : 2026-08-09
Statut : validé (brainstorm)
Fil : transverse « Oracle / Éphémères » (hors train de macros)
Sous-projet : **SP2 — Consommateur backend** (suit SP1 producteur, précède SP3 app)
Références : SP1 [`2026-08-09-oracle-base-commune-design.md`](2026-08-09-oracle-base-commune-design.md) · contrat [`oracle/README.md`](../../../oracle/README.md) · genèse [`oracle-genese.md`](../../project/oracle-genese.md) · ADR [`2026-07-24`](../../project/decisions.md)

## Objectif

Faire du backend Pi un **consommateur** de `reference.sqlite` v2 : il télécharge
l'artefact publié par SP1, l'interroge hors-ligne, et abandonne sa source de
catalogue propre (`seed_stars.sql` / table `catalog_objects` de `state.db`). À la
fin de SP2, le backend sert le **catalogue complet toutes familles** (comètes,
planètes, Lune, Soleil, deep-sky Messier/NGC/IC, étoiles) et **pointe n'importe
quel objet par son id**, sans régression de l'API vis-à-vis de l'app (que SP3
adaptera au nouveau contrat).

SP2 ne touche **pas** l'UI (SP3), les notifications, ni le producteur (SP1 est
livré et vérifié en CI le 2026-08-09 : artefact v2 publié, 953 comètes + 12952
deep-sky + 451 étoiles + 7 planètes + Lune + Soleil, Messier = 110).

## Décisions de conception (issues du brainstorm)

1. **Périmètre SP2 = bascule catalogue complète + GoTo par id + garde solaire.**
   L'interpolation des éphémères à l'instant courant est le cœur : elle est de
   toute façon exigée dès la bascule catalogue (pour `visible_now`), donc y greffer
   la résolution GoTo est peu coûteux. Découper « catalogue seul, GoTo plus tard »
   serait une fausse économie (l'interpolateur reste requis, mais le GoTo éphémère
   resterait cassé entre deux tranches).
2. **L'`id` est le vocabulaire partagé app ↔ Pi.** Les deux référencent les mêmes
   `objects.id` de `reference.sqlite`. Conséquence : `/goto` passe de « RA/Dec
   brut » à « id résolu côté Pi ».
3. **Stockage : fichier séparé, connexion RO dédiée.** `reference.sqlite` est caché
   dans le state dir (`/var/lib/astro-brain/reference.sqlite`) mais en **fichier
   distinct de `state.db`**, lu par une **2ᵉ connexion aiosqlite en lecture seule**
   — **pas d'`ATTACH`**. Les deux bases ont des cycles de vie opposés : `state.db`
   est précieuse/RW/migrée/Pi-owned ; `reference.sqlite` est **jetable/RO/remplacée
   en bloc**. Les coupler compliquerait le remplacement atomique.
4. **Sync online-first, non-bloquante.** Aucun binaire bundlé (14 Mo en git
   contrediraient la publication par release asset de SP1). Un Pi neuf jamais
   synchronisé et hors-ligne a un **catalogue vide** assumé (`reference_ready =
   false`) ; le Pi est en ligne à la maison au setup (workflow sync GPS/heure déjà
   en place). La sync boot tourne en **tâche de fond du lifespan** (comme le
   superviseur monture) → un réseau lent/absent ne retarde jamais le démarrage.
5. **`/goto` id-only.** Aucun client ne poste de coords libres aujourd'hui (le
   wizard d'alignement utilise `sync_radec`, pas `/goto`). Contrat plus simple et
   le garde solaire s'applique **toujours** (pas de chemin coords-brut qui le
   contourne). Le futur plate-solving (Macro 5) sera un **chemin distinct**.
6. **Garde solaire = verrou d'exécution côté backend.** L'app porte l'avertissement
   humain (SP3) ; le backend refuse un GoTo `kind='sun'` tant que
   `confirm_solar=true` n'est pas passé (erreur `solar_ack_required`), comme il
   refuse déjà un GoTo non-aligné.
7. **`kind` = vocabulaire v2.** `comet | planet | moon | sun | dso | star`. Messier
   n'est plus un `kind` : c'est le sous-ensemble `dso` où la colonne `messier` est
   non-nulle. SP3 adaptera l'app.
8. **`visible_now` inchangé = alt > 0.** Le raffinement « au-dessus de l'horizon
   *pendant la nuit astronomique* » (via la position du Soleil déjà dans la base)
   est **différé** — préoccupation planning/UI (SP3).
9. **Wizard 3 étoiles laissé tel quel.** Il garde sa source propre
   (`_alignment_stars.json`) — autre sous-système, hors mandat SP2. Entorse au
   « une seule source » **notée au backlog** pour une passe ultérieure.

## Le contrat consommateur : lecture de `reference.sqlite` v2

Le backend lit le schéma v2 (source de vérité : `oracle/schema.sql`) et n'en
consomme, pour SP2, que : `meta`, `objects`, `fixed_object`, `ephemeris`.
`comet_elements` n'est pas nécessaire (les samples pré-calculés suffisent).

- **Fixes** (`dso`, `star`) : `fixed_object.ra_deg/dec_deg` (of-date JNow),
  `apparent_mag`, `object_type`, `size_arcmin`, `constellation`, `messier`,
  `ngc_ic`.
- **Éphémères** (`comet`, `planet`, `moon`, `sun`) : samples journaliers
  `ephemeris(sample_utc, ra_deg, dec_deg, apparent_mag, illumination,
  constellation)` sur `[meta.window_start, meta.window_end]`.
- **Garde de version** : constante `SUPPORTED_SCHEMA_VERSION = 2`. Le backend
  **refuse d'adopter** un artefact `meta.schema_version > 2` (garde l'ancien cache
  + warning). Un artefact `< 2` n'existe plus en prod (release v2).

## Sync de l'artefact

```
[boot, tâche de fond]  ou  [POST /reference/sync]
  GET manifest.json  (URL en env, défaut = asset release almanac-latest)
    ├─ échec réseau → no-op, on garde le cache (log warning)
    └─ ok → manifest.sqlite_sha256 == sha256(cache local) ?
              ├─ oui → no-op (déjà à jour)
              └─ non → GET reference.sqlite (14 Mo)
                        → vérif sha256 == manifest (sinon rejet)
                        → vérif schema_version <= 2 (sinon rejet, garde cache)
                        → écriture fichier temp + fsync + rename atomique
                        → réouverture connexion RO (sous lock) + swap du handle
```

- **Config** : `ASTRO_BRAIN_REFERENCE_MANIFEST_URL` (défaut = URL du `manifest.json`
  de la release `almanac-latest`) ; chemin cache dérivé du state dir
  (`reference.sqlite` à côté de `state.db`).
- **Remplacement transparent** : les providers récupèrent le handle courant via un
  petit accesseur → un swap post-sync est invisible pour les requêtes suivantes.
- **Pas de polling périodique** : cadence producteur hebdo → boot + `POST
  /reference/sync` (déclenchable par l'app) suffisent.

## API (changements)

### `GET /catalog/objects` (et `/catalog/objects/{id}`)
- **Source** : `reference.sqlite` (plus `state.db`).
- **`kind`** : vocabulaire v2 (`comet|planet|moon|sun|dso|star`). Filtre Messier =
  `kind=dso` + `messier` non-nul.
- **Champs ajoutés** au `CatalogObject` : `messier`, `ngc_ic`, `illumination`
  (Lune/Vénus/Mercure ; NULL sinon). Inchangés : `ra_deg/dec_deg` (**interpolés à
  maintenant pour les éphémères**), `apparent_mag`, `constellation`, `object_type`,
  `size_arcmin`, `altitude_deg/azimuth_deg` (enrichissement `visible_now`).
- **Éphémère hors-fenêtre** (cache périmé) : servi sans alt/az (pas d'extrapolation)
  et exclu par `visible_now`.
- **`reference_ready = false`** : réponses 200 à liste **vide** (dégradation propre).

### `POST /goto` — **changement de contrat**
- Corps : `{ id: str, confirm_solar?: bool }` (remplace `{ra_deg, dec_deg,
  target_name?}`).
- Résolution : `id` → `objects.kind` →
  - fixe → RA/Dec de `fixed_object` ;
  - éphémère → RA/Dec **interpolé à maintenant** depuis `ephemeris`.
- `target_name` (affichage monture) auto-rempli depuis `objects.name/designation`.
- Gardes (ordre) : `404 unknown_id` ; `409 reference_unavailable` (base non prête) ;
  `409 ephemeris_stale` (éphémère hors `[window_start, window_end]`) ; `409
  not_aligned` (existant) ; `409 goto_in_progress` (existant) ; `409
  solar_ack_required` (`kind='sun'` sans `confirm_solar=true`). Puis
  `mount.goto_radec(ra, dec, target_name=…)` (inchangé).

### `POST /reference/sync` — **nouveau**
- Déclenche une sync (voir plus haut), renvoie l'état résultant (`updated` /
  `up_to_date` / `offline` / `rejected_schema`).

### État de référence (surfacage)
- Exposer `reference_ready`, `schema_version`, `generated_at`, `window_start/end`
  de l'artefact courant. **Emplacement à trancher au plan** (nouveau
  `GET /reference/status` vs extension de `GET /about`).

## Interpolation (éphémères → RA/Dec à l'instant courant)

- **Linéaire** entre les deux samples journaliers encadrant `now`.
- **Wrap RA** : interpolation sur le plus court arc (gère 359°→1° sans téléporter).
- **Hors-fenêtre** : refus (pas d'extrapolation) → `ephemeris_stale` (GoTo) / non
  enrichi (liste). Les fixes ne sont jamais concernés.
- Réutilise `services/_ephemeris.py::sky_az_alt_from_ra_dec` pour l'alt/az **après**
  résolution du RA/Dec courant (pas de nouvelle trigo).

## Architecture code (backend)

- **`repository/reference_db.py`** (nouveau) : chemin cache, ouverture connexion
  **RO** aiosqlite (`mode=ro`), accesseur du handle courant + lock de swap,
  lecture `meta`.
- **`services/reference/sync.py`** (nouveau) : fetch manifest (httpx, déjà dep),
  compare sha256, download, vérif sha256 + `schema_version`, rename atomique,
  réouverture. Tâche de fond enregistrée dans le lifespan (`app.py`) + endpoint
  `POST /reference/sync`.
- **`services/catalog/providers.py`** (refonte) : deux providers lisant la connexion
  RO référence — **`FixedObjectProvider`** (`dso`/`star` → `fixed_object`) et
  **`EphemerisProvider`** (`comet`/`planet`/`moon`/`sun` → `ephemeris` interpolé à
  maintenant). Remplacent `SqliteCatalogProvider(state.db)`.
- **`services/catalog/interpolation.py`** (nouveau) : interpolation linéaire +
  wrap RA + détection hors-fenêtre. Pure, testable isolément.
- **`services/catalog/resolver.py`** (nouveau) : `id → (ra, dec, kind, name)` pour
  le GoTo (partage l'interpolation).
- **`routes/goto.py`** : nouveau contrat id-only + gardes (dont solaire).
- **`app.py`** : retrait de l'appel `apply_seeds` + du provider star `state.db` ;
  câblage des nouveaux providers sur la connexion référence + de la tâche sync.
- **Migration `_004_drop_catalog_objects.py`** : DROP `catalog_objects` (forward-only).
- **Suppressions** : `data/seed_stars.sql`, `tools/seed_stars.py`,
  `services/catalog/seed_runner.py` et les 3 tests associés
  (`test_catalog_seed_runner.py`, `test_catalog_seed_stars_smoke.py`,
  `test_seed_stars_tool.py`).

## Tests (TDD, offline déterministe)

Fixture : un **petit `reference.sqlite` v2 construit en test** via SQL brut (schéma
v2 + quelques lignes par famille) — pas d'import d'`oracle/`, pas de binaire commité.

- **Sync** : manifest inchangé → no-op ; changé → download + vérif sha + swap ;
  offline → cache conservé, aucune erreur ; `schema_version=3` → rejet, cache gardé ;
  sha mismatch → rejet.
- **Interpolation** : valeur entre deux samples connus ; wrap RA 359°↔1° ; `now`
  hors fenêtre → refus.
- **Providers** : `FixedObjectProvider` (query dso/star, filtre Messier, `max_mag`,
  `search`) ; `EphemerisProvider` (RA/Dec interpolé à `now`, `illumination`
  présente pour la Lune).
- **`GET /catalog/objects`** : familles présentes ; `visible_now` (alt>0) ;
  `reference_ready=false` → liste vide 200.
- **`POST /goto`** : id fixe résolu ; id éphémère interpolé ; `unknown_id` 404 ;
  `not_aligned`/`goto_in_progress` 409 (inchangés) ; `solar_ack_required` sans
  `confirm_solar` puis succès avec ; `ephemeris_stale` hors fenêtre ;
  `reference_unavailable` base absente.
- **Migration** `_004` : `catalog_objects` absente après migration ; `state.db`
  intacte par ailleurs.

## Flux

```
[GitHub Release almanac-latest]  reference.sqlite v2 + manifest.json (SP1)
        │ (sync conditionnelle sha256, online-first)
        ▼
[Pi backend]  /var/lib/astro-brain/reference.sqlite (RO, jetable)   state.db (RW, Pi-owned)
   providers fixe/éphémère ── interpolation ──┐
   GET /catalog/objects (id, kind v2, alt/az) │
   POST /goto {id, confirm_solar} ── resolver ─┴─▶ mount.goto_radec(ra,dec) ─▶ monture
   POST /reference/sync (refresh manuel)
        ▲ REST (app SP3)
```

## Hors périmètre SP2 (→ SP3 / plus tard)

- **App Flutter** : sync/cache app, UI catalogue toutes familles, **avertissement
  solaire humain**, projection alt/az côté app, notifications locales (SP3).
- **Nuit astronomique** via position du Soleil (raffinement `visible_now`).
- **Plate-solving** (chemin GoTo par coords, Macro 5).
- **Unification de la source d'étoiles du wizard 3 étoiles** (`_alignment_stars.json`)
  — backlog « une seule source ».
- **`comet_elements`**, événements/appulses (`events`) — tranches ultérieures.

## Questions ouvertes (à trancher au plan)

1. **Surfacage de l'état référence** : nouveau `GET /reference/status` vs champs
   ajoutés à `GET /about`.
2. **Coût liste** : interpoler RA/Dec de ~953 comètes à chaque `GET /catalog/objects`
   avec `visible_now` sur Pi 3 B+ — trivial en calcul (interpolation linéaire) mais
   à mesurer ; éventuel index/limite par défaut à confirmer.
3. **Forme exacte de la fixture de test** (helper SQL vs petit fichier généré au
   setup de test).
