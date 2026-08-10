# Oracle SP3-A — Mise à niveau du contrat app (design)

> Statut : design validé (2026-08-10). Slice A du sous-projet SP3 « app
> consommatrice de `reference.sqlite` ». Prochaine étape : plan
> d'implémentation (`superpowers:writing-plans`).

## Contexte

SP2 a livré le backend consommateur (mergé sur `main`) : le catalogue et le
GoTo sont désormais servis depuis `reference.sqlite` (almanach produit par
SP1). Le contrat a changé de façon **rompante** pour l'app Flutter, qui n'a pas
suivi :

- **GoTo cassé** : l'app poste encore `POST /goto {ra_deg, dec_deg,
  target_name}` ; le backend attend `POST /goto {id, confirm_solar}`.
- **DTO catalogue incomplet** : le backend expose des champs v2 (`messier`,
  `ngc_ic`, `illumination`, `angular_size_arcmin`, `ephemeris_stale`) que le
  DTO app ignore.
- **Avertissement solaire absent** : le backend refuse un GoTo Soleil sans
  acquittement (`409 solar_ack_required`) ; aucune UI côté app.
- **État référence non surfacé** : l'app n'a aucune notion de `reference.sqlite`
  (fraîcheur, fenêtre couverte, resync).

SP3 tel que la roadmap le décrit (cache local + planif hors ligne + projection
alt/az client + notifs) couvre plusieurs sous-systèmes indépendants. Décision
de découpage (2026-08-10) : livrer d'abord **A** (contrat correct, app pilotable
online), puis construire les slices offline par-dessus.

## Périmètre

### Dans A
- Rendre l'app **correcte** contre le contrat SP2, en restant client REST
  **online** du Pi (aucune infra locale nouvelle).
- GoTo par `id` + flux d'avertissement solaire.
- DTO catalogue complété aux champs v2.
- Feedback GoTo qui ne détruit plus la liste ; mapping `detail → message` FR.
- Statut référence + resync (tuile Setup + bannière Catalogue).
- Catalogue « A-lite+ » : filtre par famille (`kind`) + toggle Messier + copie
  corrigée.

### Hors A (slices SP3 ultérieures, non traitées ici)
- Cache `reference.sqlite` **local** dans l'app (download / vérification sha256
  / swap atomique ; aucune dépendance sqflite/drift/download aujourd'hui).
- Projection alt/az **côté client** (port Dart de la trigo backend) pour le
  hors-ligne Pi éteint.
- Night planner offline (« observable cette nuit »).
- Refonte UX **par famille** (cartes planète, phase de Lune via `illumination`,
  cartes DSO/comète dédiées).
- Notifications locales (dépendent d'événements pas encore produits par Oracle).

## Contrat backend (référence, tel que mergé sur `main`)

Source : `backend/astro_brain/routes/{goto,catalog,reference}.py`,
`backend/astro_brain/services/catalog/models.py`.

**`GET /catalog/objects`** — query : `kind?`, `search?`, `max_mag?`,
`messier` (bool, défaut false), `visible_now` (bool, défaut false), `limit`
(1–500, défaut 100), `offset` (≥0, défaut 0). Réponse :
`{objects: CatalogObject[], count, limit, offset}`.

**`CatalogObject`** : `qualified_id`, `kind`
(`comet|planet|moon|sun|dso|star`), `name`, `designation?`, `ra_deg`,
`dec_deg`, `mag?`, `constellation?`, `object_type?`, `angular_size_arcmin?`,
`messier?`, `ngc_ic?`, `illumination?`, `ephemeris_stale` (bool),
`altitude_deg?`, `azimuth_deg?`, `extras` (dict).

**`GET /catalog/objects/{qualified_id:path}`** → `CatalogObject` ou `404`.

**`POST /goto`** — body `{id: str, confirm_solar: bool = false}` → `200 OkResponse`.
Erreurs (`HTTPException.detail`) :

| Statut | `detail`             | Sens                                             |
|--------|----------------------|--------------------------------------------------|
| 409    | `reference_unavailable` | `reference.sqlite` absent/non ouvert          |
| 404    | `unknown_id`         | `id` inconnu du résolveur                         |
| 409    | `ephemeris_stale`    | échantillon éphéméride périmé pour cet objet      |
| 409    | `not_aligned`        | monture non alignée                               |
| 409    | `goto_in_progress`   | un GoTo est déjà en cours                         |
| 409    | `solar_ack_required` | cible `kind==sun`, `confirm_solar` non fourni     |

**`GET /reference/status`** → `{ready, schema_version?, generated_at?,
window_start?, window_end?}`. **`POST /reference/sync`** →
`{status, schema_version?}`.

> L'état référence **ne transite pas** par le SSE `/state` : il se lit à la
> demande via `GET /reference/status`.

## Décisions actées

- **Avertissement solaire : server-driven.** L'app envoie toujours
  `confirm_solar:false` d'abord ; sur `409 solar_ack_required` elle ouvre le
  dialogue puis renvoie `confirm_solar:true`. L'app ne code pas en dur la
  politique « quoi est dangereux » — le backend reste la source de vérité
  (robuste si Oracle étend l'avertissement). Coût : un aller-retour perdu sur
  un objet solaire (négligeable).
- **Catalogue A-lite+.** Filtre `kind` + toggle Messier + copie neutre. La
  refonte UX par famille est reportée à une slice ultérieure.

## Design par composant

### 1. `ApiService` — propager le `detail`

**Fichier** : `app/lib/services/api_service.dart`.

`ApiException` gagne un champ `detail: String?`. Sur non-200, on tente de
décoder `{"detail": "..."}` du corps (best-effort ; si le corps n'est pas ce
JSON, `detail` reste `null`, `statusCode` inchangé). `postJson`/`_post`/`getJson`
alimentent ce champ. Aucun changement de signature publique cassant : `message`
et `statusCode` restent.

**Raison** : sans le `detail`, l'app ne peut pas distinguer
`solar_ack_required` de `not_aligned`/`goto_in_progress`/etc. C'est le
prérequis du flux solaire et du mapping d'erreurs.

### 2. `CatalogObjectDto` — champs v2

**Fichier** : `app/lib/features/catalogue/catalogue_models.dart`.

Ajout des champs (tous nullable sauf le flag) :

| Champ Dart          | Clé JSON             | Type      |
|---------------------|----------------------|-----------|
| `messier`           | `messier`            | `String?` |
| `ngcIc`             | `ngc_ic`             | `String?` |
| `illumination`      | `illumination`       | `double?` |
| `angularSizeArcmin` | `angular_size_arcmin`| `double?` |
| `ephemerisStale`    | `ephemeris_stale`    | `bool` (défaut `false`) |

`objectType`/`altitudeDeg`/`azimuthDeg` restent. `fromJson` et `props`
(equatable) sont étendus en conséquence. `isVisible` inchangé (altitude > 0).

### 3. GoTo par `id`

**Fichiers** : `catalogue_repository.dart`, `catalogue_event.dart`,
`catalogue_bloc.dart`, `widgets/catalogue_detail_sheet.dart`,
`catalogue_screen.dart`.

- `CatalogueRepository.goto(String id, {bool confirmSolar = false})` →
  `POST /goto {id, confirm_solar}`.
- `GoToRequested(String id, {bool confirmSolar = false})` remplace le triplet
  `raDeg/decDeg/targetName`. L'`id` vient de `object.qualifiedId` (déjà présent
  dans le DTO).
- La slew bar continue de lire le nom de cible via le SSE
  (`gotoTarget['target_name']`, rempli côté backend par
  `mount.goto_radec(..., target_name=target.name)`) — **aucun changement**.
- `AbortRequested` → `POST /stop` — inchangé.

### 4. Feedback GoTo (ne plus détruire la liste)

**Fichiers** : `catalogue_bloc.dart`, `catalogue_state.dart`,
`catalogue_screen.dart`.

Bug pré-existant : `_onGoTo` en erreur émet `CatalogueError`, que `_ObjectList`
rend en remplaçant **toute** la liste par un texte centré. Un GoTo rejeté ne
doit pas effacer le catalogue.

Design : le résultat d'un GoTo passe par un **canal transitoire** distinct de
l'état liste. Concrètement, un `CatalogueGotoOutcome` (one-shot) porté par un
`BlocListener` en tête d'écran, rendu en `SnackBar`. Le `switch` de
`_ObjectList` sur `CatalogueState` n'est plus impacté par un échec de GoTo
(la liste chargée reste affichée). Mapping `ApiException.detail → message` FR :

| `detail`               | Message                                             |
|------------------------|-----------------------------------------------------|
| `solar_ack_required`   | *(pas un message — déclenche le dialogue solaire)*  |
| `reference_unavailable`| « Almanach indisponible — lance une resync. »       |
| `ephemeris_stale`      | « Éphémérides périmées pour cet objet. »            |
| `not_aligned`          | « Monture non alignée — aligne d'abord. »           |
| `goto_in_progress`     | « Un GoTo est déjà en cours. »                      |
| `unknown_id`           | « Objet introuvable côté monture. »                 |
| *(autre / réseau)*     | « GoTo impossible : {message}. »                    |

> Choix d'implémentation laissé au plan : `CatalogueGotoOutcome` comme état
> transitoire ré-émettant l'état liste courant, ou stream/callback dédié. Le
> comportement observable (liste préservée, SnackBar, dialogue solaire) est le
> contrat.

### 5. Flux d'avertissement solaire (server-driven)

**Fichiers** : `catalogue_bloc.dart`, `catalogue_screen.dart`, nouveau widget
de dialogue.

1. `POINTER` → `GoToRequested(id, confirmSolar:false)`.
2. Bloc appelle `repo.goto(id, confirmSolar:false)`.
3. Sur `ApiException(detail == 'solar_ack_required')` : le bloc émet un
   `CatalogueGotoOutcome` de type « demande d'acquittement solaire » portant
   l'`id`.
4. Le `BlocListener` ouvre un **dialogue d'avertissement** (danger oculaire /
   instrument, texte explicite, bouton destructif « Pointer quand même » +
   « Annuler »).
5. Confirmation → `GoToRequested(id, confirmSolar:true)` → renvoi avec
   `confirm_solar:true`.

Aucune politique solaire codée en dur côté app : c'est le backend qui décide
qu'un acquittement est requis.

### 6. Statut référence + resync

**Fichiers** : nouveau `app/lib/features/setup/reference/` (repository + tuile),
bannière dans `catalogue_screen.dart`, câblage DI dans `app/lib/app.dart`.

- `ReferenceRepository` : `getStatus()` → `GET /reference/status` ;
  `sync()` → `POST /reference/sync`. DTO miroir de `ReferenceStatus` /
  `SyncResponse`.
- **Tuile Setup → « Almanach »** : affiche `generated_at` (généré le…),
  `window_start`–`window_end` (couvre du… au…), état `ready`, + bouton
  « Resynchroniser » (déclenche `POST /reference/sync`, puis relit le statut).
- **Bannière Catalogue** : si `ready == false`, bandeau explicite (« Almanach
  indisponible — le pointage et le catalogue sont hors service. Resynchronise
  dans Réglages. »). Lecture **à la demande** (au chargement de la page), pas
  via SSE.

> Réactivité SSE de l'état référence : hors périmètre A (le backend ne le
> publie pas sur `/state`). Fold éventuel dans le SSE noté au backlog.

### 7. Catalogue A-lite+

**Fichiers** : `catalogue_screen.dart` (filtres + copie),
`catalogue_event.dart` / `catalogue_state.dart` / `catalogue_repository.dart`
(filtres `kind` + `messier`).

- `listObjects` accepte `kind?` et `messier` (bool) et les passe en query.
- `CatalogueFilters` gagne `kind?` (`null` = toutes familles) et
  `messierOnly` (bool). Événements associés : `KindFilterChanged`,
  `MessierToggled`.
- UI : sélecteur de famille (chips ou dropdown, familles v2 avec libellés FR)
  + chip « MESSIER ». Copie du champ de recherche : « Rechercher un objet… ».
- Les chips MAG≤2/≤3 et « VISIBLE MAINTENANT » restent. Le filtre constellation
  côté app reste inchangé.

## Flux de données

```
Detail sheet [POINTER]
  → CatalogueBloc GoToRequested(id, confirmSolar:false)
    → CatalogueRepository.goto → POST /goto {id, confirm_solar:false}
      ├─ 200 → slew bar via SSE /state (gotoInProgress, target_name)
      ├─ 409 solar_ack_required → CatalogueGotoOutcome(solarAck, id)
      │     → dialogue → GoToRequested(id, confirmSolar:true) → POST … true → 200
      └─ 404/409 autre → CatalogueGotoOutcome(error, message FR) → SnackBar
                          (liste préservée)

Catalogue open / Setup open
  → ReferenceRepository.getStatus → GET /reference/status
    → bannière (ready?) / tuile Setup (generated_at, window)
Setup [Resynchroniser]
  → ReferenceRepository.sync → POST /reference/sync → relit getStatus
```

## Gestion des erreurs

- Réseau / Pi injoignable : timeout 3 s existant → `ApiException` sans `detail`
  → message générique. Comportement inchangé ailleurs dans l'app.
- GoTo : mapping du §4 ; jamais de destruction de la liste.
- `reference/status` en échec réseau : la bannière n'affiche pas de faux
  « indisponible » sur simple timeout — distinguer « backend dit ready:false »
  de « backend injoignable » (ce dernier relève de l'indicateur global existant).
- `reference/sync` : le backend renvoie un `status` ; l'app affiche le résultat
  (succès / inchangé / erreur) sans bloquer l'UI.

## Tests

Miroir 1:1 de `lib` sous `test/`, `mocktail` + `bloc_test`, MockBloc pour les
widgets câblés à un bloc async (jamais taper un bouton relié à un vrai bloc).

- **`ApiService`** : non-200 avec corps `{"detail":"x"}` → `ApiException.detail
  == 'x'` ; corps non-JSON → `detail == null`.
- **`CatalogObjectDto.fromJson`** : champs v2 présents / absents (nullables) ;
  `ephemeris_stale` défaut false ; `props` couvre les nouveaux champs.
- **`CatalogueRepository.goto`** : envoie `{id, confirm_solar}` (pas
  ra/dec/name).
- **`CatalogueBloc`** (bloc_test) :
  - GoTo OK → aucun `CatalogueError`, liste préservée.
  - GoTo `not_aligned`/`goto_in_progress`/`ephemeris_stale`/
    `reference_unavailable` → `CatalogueGotoOutcome(error)` avec le bon message,
    liste préservée.
  - GoTo `solar_ack_required` → `CatalogueGotoOutcome(solarAck)` ; puis
    `GoToRequested(confirmSolar:true)` → OK.
  - `KindFilterChanged`/`MessierToggled` → requête avec les bons params.
- **`ReferenceRepository`** : parse status / sync.
- **Widgets** (MockBloc) : bannière visible ssi `ready==false` ; dialogue
  solaire sur outcome `solarAck` ; SnackBar sur outcome `error` ; tuile Setup
  rend `generated_at`/fenêtre + déclenche `sync`.

## À mettre à jour à la livraison

- `docs/project/roadmap.md` : SP3-A livré (ligne transverse Oracle).
- `docs/project/journal.md` : entrée de session.
- Backlog : fold éventuel de l'état référence dans le SSE `/state` ; refonte
  UX catalogue par famille (slice suivante) ; arbitrage source étoiles wizard
  vs `reference.sqlite kind=star`.
