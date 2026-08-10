# Oracle SP3-B — Catalogue local hors ligne (design)

> Statut : design validé (2026-08-10). Slice B du sous-projet SP3 « app
> consommatrice de `reference.sqlite` ». Suit SP3-A (contrat online, mergé
> `main`). Prochaine étape : plan d'implémentation
> (`superpowers:writing-plans`).

## Contexte

SP3-A a rendu l'app **correcte** contre le contrat SP2, mais toujours
**online** : le catalogue et la visibilité sont servis par le Pi
(`GET /catalog/objects`), la fraîcheur de l'almanach par le Pi
(`GET /reference/status`), la resync par le Pi (`POST /reference/sync`). Pi
éteint, l'app ne montre rien.

Le modèle Oracle est **local-first** : l'almanach `reference.sqlite` (artefact
SP1, publié sur une release GitHub) est **la** source de données, téléchargée
par chaque consommateur. Le Pi n'est plus un serveur de catalogue ; il garde sa
propre copie **uniquement** pour résoudre un `id` de GoTo en RA/Dec et opposer
son garde `ephemeris_stale`. SP3-B fait de l'app un consommateur autonome :

- l'app télécharge et cache sa **propre** copie de `reference.sqlite` ;
- elle lit le catalogue **localement** (recherche, familles, Messier,
  magnitude) — Pi éteint ;
- elle calcule la **visibilité « maintenant »** localement (position GPS du
  téléphone + heure), en portant la trigonométrie que le Pi exécute
  aujourd'hui côté serveur.

### Ce que SP3-B ne change PAS

- **Le GoTo reste online et inchangé.** `POST /goto {id, confirm_solar}` part
  vers le Pi, qui résout l'`id` contre **sa** copie. L'app n'a jamais besoin de
  résoudre `id → RA/Dec` : la projection portée sur le téléphone sert à
  **afficher** la visibilité, pas à piloter la monture. Pointer exige le Pi —
  c'est attendu.
- Le flux d'avertissement solaire, la slew bar, l'abort : inchangés (SP3-A).

### Rappel : pourquoi porter ~40 lignes de calcul ne renie pas Oracle

Oracle a supprimé l'**astronomie** chez les consommateurs (mécanique orbitale,
éphémérides planétaires depuis `de421.bsp`, précession/nutation J2000→of-date,
magnitude) : tout est **cuit au build** en Python/skyfield et figé en RA/Dec
apparent dans `reference.sqlite`. Ce qui reste pour **tout** consommateur est la
projection géométrique **LST → alt/az** (dépend de l'observateur ET de
l'instant : impossible à cuire au build). Le Pi la fait aujourd'hui
(`services/_ephemeris.py` + `visibility.py`). Pi éteint, le téléphone est le
seul ordinateur disponible : SP3-B y porte **exactement** ces fonctions
(~40 lignes de trigo), pas l'astronomie.

## Périmètre

### Dans B
- **Acquisition locale** : télécharger `reference.sqlite` depuis la release
  GitHub `almanac-latest` (manifest `sha256` → download conditionnel → vérif →
  swap atomique), miroir 1:1 du consommateur backend SP2
  (`services/reference/sync.py`). Refresh non bloquant au lancement (si online)
  + resync manuelle.
- **Lecture locale du catalogue** : réécriture de `CatalogueRepository` pour
  interroger le `reference.sqlite` **local** (SQL) au lieu de
  `GET /catalog/objects`. Familles (`kind`), Messier, magnitude, recherche,
  tri, pagination : portés côté app. Toutes les familles, fixes **et**
  éphémères (planètes/Lune/Soleil/comètes interpolées à l'instant), comme
  SP3-A.
- **Projection alt/az côté client** : port Dart de `_ephemeris.py`
  (`_gmst_deg` + `sky_az_alt_from_ra_dec`), **temps-paramétré** (`t` en
  argument), alimenté par `now()` + GPS téléphone (réutilise
  `PhoneLocation`). Filtre « visible maintenant » (alt > 0) et exclusion des
  `ephemeris_stale`, miroir de `visibility.py`.
- **Statut almanach local** : `ReferenceRepository` repointe sur le fichier
  **local** — `ready`/`meta` lus dans le sqlite local, resync = download
  GitHub. DTO et UI (tuile Setup « Almanach », bannière Catalogue) **inchangés**
  de forme.
- **Parité fonctionnelle SP3-A** Pi éteint (hors GoTo, qui exige le Pi).

### Hors B (slices ultérieures)
- **Nettoyage backend** (`GET /catalog/objects` retiré, le Pi ne sert plus le
  catalogue) : tranche dédiée **entre B et C** (décision utilisateur).
- **Night planner** (SP3-C) : sélecteur date/heure + classement « observable
  cette nuit ». B construit le **moteur temps-paramétré** ; C ne fait qu'ouvrir
  le curseur temps et ranger — **aucun calcul nouveau**, purement additif.
- Notifications locales (SP3-D).
- Refonte UX **par famille** (déjà reportée en SP3-A).
- Exécution du moteur sur un isolate dédié si le volume l'exige (voir
  Gestion des erreurs → performance) : backlog, pas B.

## Contrat producteur (référence, tel que publié)

### `manifest.json` (release GitHub `almanac-latest`)
Émis par `oracle/oracle/manifest.py`. Clés :
`schema_version` (int), `generated_at` (ISO-8601 UTC), `sqlite_url` (str),
`sqlite_sha256` (hex), `window_start`, `window_end`.
URL : `https://github.com/Pascal3100/astro-brain/releases/download/almanac-latest/manifest.json`
(constante `DEFAULT_MANIFEST_URL`, `backend/.../reference_db.py`).

### `reference.sqlite` — schéma (`oracle/schema.sql`, `schema_version = 2`)
- **`meta`** : `schema_version` (un consommateur **refuse** une version > 2),
  `generated_at`, `window_start`, `window_end` (fenêtre glissante ~60 j),
  `skyfield_kernel`.
- **`objects`** : `id` (PK — `NGC1976` / `planet:mars` / `moon` / `sun` /
  `star:HIP32349` / MPC packé), `kind`
  (`comet|planet|moon|sun|dso|star`), `name?`, `designation?`.
- **`fixed_object`** (dso + star) : `object_id` (PK→objects), `ra_deg`,
  `dec_deg` (of-date JNow), `apparent_mag?`, `object_type?`, `size_arcmin?`,
  `constellation?`, `messier?`, `ngc_ic?`.
- **`ephemeris`** (comet+planet+moon+sun) : `(object_id, sample_utc)` PK,
  `ra_deg`, `dec_deg` (of-date, **pas** intended for exact of-date, échantillon
  journalier), `earth_dist_au?`, `sun_dist_au?`, `apparent_mag?`,
  `illumination?`, `constellation?`. Index `idx_ephem_time`.
- **`comet_elements`** : éléments orbitaux (non lus par le catalogue app).

## Décisions actées

- **Local-first, Pi source de données.** L'app possède sa propre copie ;
  le Pi garde la sienne pour résoudre les GoTo (`id → RA/Dec`) + garde
  `ephemeris_stale`. Le Pi n'est plus interrogé pour le catalogue/visibilité.
- **Moteur temps-paramétré dès B.** La projection prend `t` en argument ; B ne
  l'exerce qu'à `now()`. Le sélecteur date/heure et le classement « observable
  cette nuit » sont **SP3-C**, additifs sur le même moteur — pas de refonte
  entre B et C.
- **Éphémères inclus en B.** Planètes/Lune/Soleil/comètes sont interpolées à
  l'instant (miroir de `EphemerisProvider`), pour la parité avec SP3-A. Un objet
  hors fenêtre est `ephemeris_stale` (exclu du « visible maintenant »).
- **Port fidèle, pas réinvention.** `interpolation.py`, `_ephemeris.py`,
  `providers.py`, `visibility.py` sont portés **à l'identique** en Dart (mêmes
  formules, mêmes clauses SQL, mêmes bornes de fenêtre), pour que l'app et le Pi
  s'accordent sur RA/Dec et `stale`.
- **sqlite : `sqlite3` (FFI) + `sqlite3_flutter_libs`.** On ouvre un fichier
  **existant en lecture seule** (`mode=ro`), SQL brut — pas d'ORM, pas de
  codegen. `drift` (codegen/migrations) est surdimensionné ; `sqflite`
  (async, orienté DB gérée par l'app, pas d'ouverture RO immuable directe) ne
  colle pas à « ouvrir un artefact jetable ». `sqlite3` reflète le
  `mode=ro&immutable=1` du backend.
- **Acquisition = miroir du backend SP2.** Mêmes statuts (`updated`,
  `up_to_date`, `offline`, `rejected_schema`, `rejected_hash`), même garde
  `schema_version ≤ 2`, même swap atomique. Pas de seed embarqué dans l'APK :
  premier lancement = un download (option B, l'utilisateur a le WiFi/5G à
  l'install).

## Architecture

Deux nouveaux modules app + réécriture interne de deux repositories. La
**surface publique** de `CatalogueRepository`/`ReferenceRepository` (signatures,
DTO) ne bouge quasi pas → blocs, UI et tests widget SP3-A **inchangés**.

```
app/lib/
  oracle_cache/                    (NOUVEAU — acquisition)
    almanac_store.dart             chemin local (path_provider), sha256, handle DB
    manifest_dto.dart              DTO manifest.json
    almanac_sync.dart              fetch/verify/swap atomique  ← miroir sync.py
  features/catalogue/
    local/                         (NOUVEAU — moteur lecture + visibilité)
      local_reference_db.dart      ouverture RO du sqlite local (sqlite3)   ← reference_db.py
      sky_projection.dart          Observer + gmstDeg + skyAzAltFromRaDec    ← _ephemeris.py
      ephemeris_interpolation.dart parseUtc/lerp/lerpAngleDeg/interpolateRaDec ← interpolation.py
      catalogue_providers.dart     FixedObjectProvider + EphemerisProvider   ← providers.py
      local_catalogue.dart         façade list/getById (merge+tri+pagination) ← reference_catalog.py
      visibility.dart              enrichissement alt/az + filtre visible_now ← visibility.py
    catalogue_repository.dart      RÉÉCRIT : lit `local/`, GoTo reste online
  features/setup/reference/
    reference_repository.dart      RÉÉCRIT : meta locale + sync = download
```

### Flux de données (Pi éteint)

```
Lancement app
  → AlmanacSync.sync() non bloquant (si online) : manifest → sha → download? → swap → reopen
  → LocalReferenceDb.ready (fichier présent + schéma ≤ 2)

Catalogue open  (CatalogueBloc → CatalogueRepository.listObjects(...))
  → LocalCatalogue.listAll(filter)                 [SQL local, fixes + éphémères]
      FixedObjectProvider   : SELECT … fixed_object JOIN objects  (kind/mag/messier/search)
      EphemerisProvider     : SELECT … ephemeris   (fenêtre ±1j12h)  → interpole à now → stale?
  → Visibility.enrich(objects, visibleNow, gps=PhoneLocation.current(), t=now())
      skyAzAltFromRaDec(ra,dec,observer,t)  → altitude_deg/azimuth_deg ; filtre alt>0 si visibleNow
  → CatalogObjectDto[]  (même forme qu'en SP3-A)  → bloc → UI  (INCHANGÉ)

GoTo  (inchangé, EXIGE le Pi)
  → CatalogueRepository.goto(id, confirmSolar) → POST /goto → Pi résout id contre SA copie

Almanach (Setup / bannière)
  → ReferenceRepository.getStatus() → LocalReferenceDb.meta() (schema/generated_at/window)
  → ReferenceRepository.sync()      → AlmanacSync.sync() (download GitHub) → relit meta
```

## Design par composant

### 1. `oracle_cache/manifest_dto.dart` (NOUVEAU)

DTO immuable (`Equatable`) miroir de `manifest.json` :

| Dart               | Clé JSON          | Type     |
|--------------------|-------------------|----------|
| `schemaVersion`    | `schema_version`  | `int`    |
| `generatedAt`      | `generated_at`    | `String` |
| `sqliteUrl`        | `sqlite_url`      | `String` |
| `sqliteSha256`     | `sqlite_sha256`   | `String` |
| `windowStart`      | `window_start`    | `String` |
| `windowEnd`        | `window_end`      | `String` |

`fromJson` lève `FormatException` si une clé requise manque (traité comme
`offline` par le sync).

### 2. `oracle_cache/almanac_store.dart` (NOUVEAU)

Isole `path_provider` et le système de fichiers.

- `Future<File> file()` → `<ApplicationDocumentsDirectory>/reference.sqlite`
  (crée le dossier au besoin).
- `Future<File> tmpFile()` → `…/reference.sqlite.tmp`.
- `Future<String?> localSha256()` → digest hex du fichier local, ou `null` s'il
  est absent (miroir `local_sha256`, streaming par blocs).
- Constante `kManifestUrl` = `DEFAULT_MANIFEST_URL` (même URL que le backend).
- `kSupportedSchemaVersion = 2`.

### 3. `oracle_cache/almanac_sync.dart` (NOUVEAU) — miroir de `sync.py`

`class AlmanacSync` : injecte un `http.Client` (fakeable), l'`AlmanacStore`, et
le `LocalReferenceDb` (pour `reopen()`). Une méthode :

```
enum AlmanacSyncStatus { updated, upToDate, offline, rejectedSchema, rejectedHash }

Future<AlmanacSyncResult> sync()   // {status, schemaVersion?}
```

Algorithme **identique** au backend :
1. GET `manifest.json` → parse. Toute erreur réseau/parse → `offline` (cache
   conservé).
2. `schema_version > 2` → `rejectedSchema` (cache conservé).
3. `localSha256() == manifest.sqliteSha256` → `upToDate` (pas de download).
4. GET `sqlite_url` → bytes en mémoire (pas de streaming, comme le backend).
5. `sha256(bytes) != manifest.sqliteSha256` → `rejectedHash` (cache conservé).
6. Écrit `reference.sqlite.tmp`, ouvre-le, lit `meta.schema_version` ; si
   absent ou `> 2` → supprime le tmp, `rejectedSchema`.
7. `tmp.rename(reference.sqlite)` (swap atomique même FS) → `LocalReferenceDb.reopen()`
   → `updated`.

### 4. `features/catalogue/local/local_reference_db.dart` (NOUVEAU) — miroir `reference_db.py`

Ouverture **lecture seule** du fichier local via `sqlite3` (FFI, synchrone).

- `void open()` : si le fichier existe, ouvre `OpenMode.readOnly` ; lit
  `SELECT schema_version FROM meta LIMIT 1` ; si absent ou `> 2`, ferme et reste
  `!ready`. Ne lève jamais (fichier absent/corrompu → `ready == false`).
- `bool get ready`.
- `Database? current()`.
- `void reopen()` : ferme puis ré-ouvre (après un swap de sync).
- `ReferenceMetaDto? meta()` : `SELECT schema_version, generated_at,
  window_start, window_end FROM meta LIMIT 1`.

> Simplification vs backend : pas de handle « stale » différé. `sqlite3` est
> synchrone (pas de requête en vol pendant un `reopen`) ; on ferme puis on
> ré-ouvre directement. Le swap n'a lieu qu'entre deux cycles de requête.

### 5. `features/catalogue/local/ephemeris_interpolation.dart` (NOUVEAU) — port de `interpolation.py`

Pur, sans I/O. Fonctions **identiques** :
- `DateTime parseUtc(String s)` — ISO-8601, suffixe `Z` accepté, tz-aware UTC.
- `double lerp(double a, double b, double frac)`.
- `double lerpAngleDeg(double a, double b, double frac)` — plus court arc,
  résultat dans `[0, 360)` : `diff = ((b - a + 180) % 360) - 180 ; (a + diff*frac) % 360`.
- `({double ra, double dec}) interpolateRaDec(before, after, DateTime t)` —
  `frac` clampé `[0,1]` ; `span == 0` → renvoie l'échantillon `before`.

### 6. `features/catalogue/local/sky_projection.dart` (NOUVEAU) — port de `_ephemeris.py`

Pur, sans I/O. **Temps-paramétré** (`t` en argument) :
- `class Observer { final double latDeg, lonDeg; }`.
- `double julianDate(DateTime tUtc)` — port de `_julian_date`.
- `double gmstDeg(DateTime tUtc)` — IAU 1982 : `T₀` à 0h UT + terme
  `1.00273790935·H` séparé (le mélange induit ~0.5° de biais — port du
  commentaire).
- `({double az, double alt}) skyAzAltFromRaDec(double raDeg, double decDeg,
  Observer o, DateTime tUtc)` — `lst = (gmst + lon) % 360` ; `ha = wrap±180(lst - ra)` ;
  `sin_alt = sin·sin + cos·cos·cos(ha)` ; `az = atan2(...) % 360` (Nord→Est).
  Clamp `sin_alt` à `[-1, 1]`.

### 7. `features/catalogue/local/catalogue_providers.dart` (NOUVEAU) — port de `providers.py`

Deux providers lisant `LocalReferenceDb.current()` et renvoyant des
`CatalogObjectDto` (le DTO SP3-A, avec `ephemerisStale`, `illumination`,
`angularSizeArcmin`, `messier`, `ngcIc`, `constellation`, `objectType`).

**`FixedObjectProvider`** (`kinds = {dso, star}`) — SQL **identique** :
`SELECT o.id,o.kind,o.name,o.designation, f.ra_deg,f.dec_deg,f.apparent_mag,
f.object_type,f.size_arcmin,f.constellation,f.messier,f.ngc_ic
FROM fixed_object f JOIN objects o ON o.id=f.object_id WHERE …`
— filtres `kind`/`max_mag`(non-null)/`messier IS NOT NULL`/`search`
(`name/designation/messier/ngc_ic LIKE %s%`), `ORDER BY (mag NULL last), mag,
name LIMIT ? OFFSET ?`. `name` défaut = `designation ?? id`.

**`EphemerisProvider`** (`kinds = {comet, planet, moon, sun}`) — port
**identique** :
- fenêtre requête `now ± (1 j 12 h)` sur `sample_utc` ;
- groupe par `object_id`, tri `sample_utc` ;
- `_build(samples, now)` : `before = échantillons ≤ now`, `after = ≥ now` ;
  `stale = !(before && after)` ; si non-stale, `interpolateRaDec(before.last,
  after.first, now)` ; si stale, échantillon-frontière le plus proche de `now`,
  RA/Dec bruts, `ephemerisStale = true` ;
- `listObjects` n'affiche **que le plaçable** : objets `stale` exclus ; puis
  filtres `max_mag`/`search` en mémoire ; tri `(mag NULL last), name` ;
  `sublist(offset, offset+limit)`.

> `get_object(id)` du backend sert le resolver GoTo côté Pi : **pas** porté en B
> (le GoTo reste online). L'app ne résout jamais un `id` localement.

### 8. `features/catalogue/local/local_catalogue.dart` (NOUVEAU) — port de `reference_catalog.py`

Façade combinant les deux providers. Entrée : un **`LocalCatalogFilter`
dédié** (miroir du `CatalogFilter` backend : `kind?`, `search`, `maxMag?`,
`messierOnly`, `limit`, `offset`) — **pas** le `CatalogueFilters` de l'UI, qui
n'a ni `limit`/`offset` (pagination différée Macro 4) ni le tri backend, et
dont le champ `constellation` est filtré côté bloc (inchangé). `listAll(filter)` :
- `!ready` → `[]` ;
- `kind != null` → délègue au provider dont le `kind` relève, sinon `[]` ;
- `kind == null` → élargit (`limit += offset, offset = 0`), concatène fixe +
  éphémère, tri `(mag NULL last, name)`, puis `sublist(offset, offset+limit)`.

### 9. `features/catalogue/local/visibility.dart` (NOUVEAU) — port de `visibility.py`

`class Visibility` : injecte `PhoneLocation` (réutilise
`features/alignment/phone_location.dart`) et une horloge `DateTime Function()`
(fakeable en tests, défaut `() => DateTime.now().toUtc()`).

`Future<List<CatalogObjectDto>> enrich(List<CatalogObjectDto> objects,
{required bool visibleNow})` — miroir exact :
- `fix = await location.current()` ; `null` → renvoie les objets tels quels
  (filtre ignoré) ;
- `Observer(lat, lon)`, `t = clock()` ;
- objet `ephemerisStale` : jamais enrichi ; exclu si `visibleNow`, sinon gardé
  tel quel ;
- sinon `skyAzAltFromRaDec` → alt/az ; si `visibleNow && alt <= 0` exclu ;
  sinon copié avec `altitudeDeg`/`azimuthDeg` renseignés.
- Seuil `kMinVisibleAltDeg = 0.0` (port de `_MIN_VISIBLE_ALT_DEG`).

### 10. `catalogue_repository.dart` (RÉÉCRIT)

- **Consomme** `LocalCatalogue` + `Visibility` (injectés) pour `listObjects`,
  au lieu de `api.getJson('/catalog/objects')`.
- **Signature publique inchangée** : `Future<List<CatalogObjectDto>>
  listObjects({String? search, double? maxMag, bool visibleNow, String? kind,
  bool messier})`. Elle construit un `LocalCatalogFilter` (avec `limit: 500,
  offset: 0`, comme le comportement online actuel), appelle
  `LocalCatalogue.listAll(...)` puis `Visibility.enrich(..., visibleNow:
  visibleNow)`. Le filtre `constellation` reste appliqué côté bloc (inchangé).
  → **`CatalogueBloc` et l'UI inchangés.**
- **`goto(id, {confirmSolar})` et `abort()` inchangés** : gardent `ApiService`
  (le GoTo reste online).

### 11. `features/setup/reference/reference_repository.dart` (RÉÉCRIT)

- `getStatus()` → lit `LocalReferenceDb.meta()` : `ready =
  LocalReferenceDb.ready` ; `schemaVersion/generatedAt/windowStart/windowEnd`
  depuis `meta` (ou `ready:false`, champs `null`, si absent). Renvoie le
  `ReferenceStatusDto` **existant** (forme inchangée).
- `sync()` → `AlmanacSync.sync()` ; mappe `AlmanacSyncStatus` → `status` du
  `ReferenceSyncResultDto` **existant** (mêmes chaînes que le backend :
  `updated`/`up_to_date`/`offline`/`rejected_schema`/`rejected_hash`).
- → **`AlmanacScreen` (tuile Setup) et `ReferenceBanner` inchangés de forme.**
  Copie à ajuster : « Resynchroniser » = télécharge depuis GitHub ; bannière
  « Almanach absent — synchronise dans Réglages » quand `ready:false`
  (premier lancement / offline sans cache).

### 12. Câblage DI (`app/lib/app.dart`)

`MultiRepositoryProvider` : instancier `AlmanacStore`, `LocalReferenceDb`
(ouvert au boot), `AlmanacSync`, `LocalCatalogue` (+ providers), `Visibility`
(avec `GeolocatorPhoneLocation`). Injecter dans `CatalogueRepository` et
`ReferenceRepository`. Déclencher `AlmanacSync.sync()` **non bloquant** au
lancement (puis `LocalReferenceDb.reopen()` est géré par le sync). `ApiService`
reste injecté pour le GoTo.

## Gestion des erreurs

- **Premier lancement / aucun cache** : `LocalReferenceDb.ready == false` →
  catalogue vide + bannière « Almanach absent ». Le sync de lancement le peuple
  si online. Aucune erreur bloquante.
- **Offline sans cache à jour** : le catalogue reste sur la **dernière** copie
  locale ; toute erreur de sync conserve le cache (`offline`).
- **Fichier corrompu / schéma > 2** : `LocalReferenceDb` reste `!ready` (jamais
  de crash) ; un download corrompu est rejeté par sha **avant** swap → le cache
  courant survit.
- **GPS indisponible** (permission refusée / timeout) : `Visibility.enrich`
  renvoie les objets sans alt/az et **ignore** le filtre `visibleNow` (miroir
  backend) — le catalogue reste consultable, la visibilité seule est dégradée.
- **GoTo Pi éteint** : `ApiException` réseau → SnackBar « GoTo impossible »
  (chemin SP3-A inchangé). Attendu : pointer exige le Pi.
- **Performance** : le catalogue est petit (centaines à bas-milliers de lignes) ;
  `sqlite3` synchrone sur l'isolate principal est acceptable. Si un volume futur
  (étoiles denses) fait sentir un jank, déplacer le moteur sur un isolate dédié
  — noté au backlog, hors B.

## Tests

Miroir 1:1 sous `test/`, `mocktail` + `bloc_test`. Les ports purs se testent
**contre les valeurs de référence du backend** (mêmes entrées → mêmes sorties).

- **`sky_projection`** : `gmstDeg` et `skyAzAltFromRaDec` sur un jeu de
  `(ra, dec, lat, lon, t)` figés, comparés aux sorties de `_ephemeris.py`
  (tolérance ≤ 1e-6°, ou arc-seconde). Cas pôle/horizon (clamp `sin_alt`).
- **`ephemeris_interpolation`** : `lerpAngleDeg` sur le passage 359°→1° ;
  `interpolateRaDec` `span == 0` ; `frac` clampé hors bornes — mêmes valeurs que
  `interpolation.py`.
- **`catalogue_providers`** (sqlite en mémoire monté depuis `oracle/schema.sql`
  + lignes fixtures) : `FixedObjectProvider` — filtres `kind`/`max_mag`/`messier`/
  `search`, tri mag-null-last ; `EphemerisProvider` — interpolation dans la
  fenêtre, `stale` hors fenêtre exclu de `listObjects`, échantillon-frontière
  pour un objet stale.
- **`local_catalogue`** : merge fixe+éphémère trié par mag ; élargissement
  `limit+offset` puis `sublist` ; `!ready → []`.
- **`visibility`** : `fix == null` → objets intacts, filtre ignoré ; `stale`
  exclu si `visibleNow`, gardé sinon ; `alt <= 0` exclu si `visibleNow` ;
  alt/az renseignés sinon.
- **`AlmanacSync`** (fake `http.Client` + FS temporaire) : sha identique →
  `upToDate`, aucun download ; sha différent → download + swap → `updated` ;
  sha du corps téléchargé faux → `rejectedHash`, cache conservé ; manifest
  `schema_version 3` → `rejectedSchema` ; erreur réseau → `offline`, cache
  conservé.
- **`LocalReferenceDb`** : fichier absent → `!ready` ; schéma 2 → `ready`,
  `meta` correcte ; schéma 3 → `!ready`.
- **`CatalogueRepository`** : `listObjects` délègue au moteur local (pas
  d'appel `/catalog/objects`) ; `goto` poste toujours `{id, confirm_solar}` au
  Pi.
- **`ReferenceRepository`** : `getStatus` lit la `meta` locale ; `sync` mappe
  les statuts d'`AlmanacSync`.
- **Widgets (MockBloc)** : inchangés de SP3-A ; ajout — bannière « Almanach
  absent » quand `ready:false` sans cache.

## Dépendances nouvelles

- `sqlite3` (bindings FFI, ouverture RO d'un fichier existant, SQL brut).
- `sqlite3_flutter_libs` (embarque la lib native SQLite pour Android).
- `path_provider` (dossier documents pour le fichier + `.tmp`).
- `geolocator` : **déjà présent** (réutilise `PhoneLocation`). `http` : **déjà
  présent** (download). Aucune régression du manifeste `INTERNET` (déjà déclaré).

## À mettre à jour à la livraison

- `docs/project/roadmap.md` : SP3-B livré (ligne transverse Oracle) ; préciser
  que le nettoyage backend (`/catalog/objects` retiré) est la tranche B↔C.
- `docs/project/journal.md` : entrée de session.
- `docs/technical/` : noter que l'app lit `reference.sqlite` en cache local
  (acquisition GitHub, projection alt/az côté client) et que le Pi ne sert plus
  le catalogue à l'app.
- `docs/project/backlog.md` : moteur sur isolate dédié si volume ; fold éventuel
  de l'état référence dans le SSE (déjà noté SP3-A) ; nettoyage backend B↔C.
</content>
</invoke>
