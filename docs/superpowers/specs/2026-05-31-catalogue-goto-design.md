# Design — Page Catalogue + GoTo réel (Macro 3 #3 + #5)

Date : 2026-05-31
Statut : validé (brainstorm)
Macro : 3 — Mise en station + GoTo basique
Items roadmap : #3 GoTo réel · #5 Page catalogue

## Objectif

Livrer la feature complète **« parcourir le catalogue → pointer un objet »** en une passe :
le GoTo réel côté backend (#3) et la page Catalogue Flutter qui le consomme (#5).
La tranche A du catalogue backend (étoiles IAU, endpoint `/catalog/objects`) est déjà
livrée (Session 23) ; ce design construit dessus.

Comportement de référence : la raquette Celestron interdit le GoTo tant que la monture
n'est pas alignée. On reproduit cette sémantique sans fermer l'accès à la consultation.

## Décisions de conception (brainstorm)

1. **Gating GoTo** : le catalogue reste toujours accessible (liste, recherche, détail).
   Si la monture n'est pas alignée : bandeau « monture non alignée » avec lien vers le
   wizard d'alignement, et bouton GoTo grisé. Le reste de la page reste interactif.
2. **Critère « aligné »** : `is_aligned` = un `AlignmentModel` a été finalisé **dans la
   session courante**. Flag en mémoire, remis à faux au démarrage du process et à la
   reconnexion de la monture (perte du modèle natif INDI). Reflète la réalité physique :
   l'alignement de ce soir tient, un redémarrage le remet à zéro.
3. **Contrat GoTo** : ce sont des coordonnées (`ra_deg`, `dec_deg` + `target_name`
   optionnel). Le mount ne connaît pas le catalogue ; la page résout l'objet → poste ses
   coordonnées et son nom.
4. **Périmètre page** : recherche texte + filtre magnitude + indicateur/filtre
   « visible maintenant » (altitude calculée via GPS + heure). Seules les étoiles sont
   seedées pour l'instant ; Messier/planètes suivront sans changement d'architecture.
5. **Visibilité — approche A** : enrichissement dans la couche catalogue (un seul
   aller-retour, aucun calcul astro côté Flutter), routine d'éphéméride isolée et testable.
6. **Mise en page** : cartes aérées (lisibilité priorisée), détail en **bottom sheet**,
   état slew avec barre de progression + bouton STOP.

## Flux

```
[Page Catalogue Flutter]
   │  GET  /catalog/objects?search=&max_mag=&visible_now=true  → liste enrichie (alt/az)
   │  POST /goto {ra_deg, dec_deg, target_name}                → lance le slew (si aligné)
   │  POST /stop                                                → abort (endpoint réutilisé)
   │  ◀── SSE /events : mount(goto_in_progress), alignment(is_aligned), gps(fix)
   ▼
[FastAPI]
   catalog router ──> VisibilityEnricher ──> _ephemeris.sky_az_alt_from_ra_dec
   goto router (garde is_aligned) ──> MountService.goto_radec ──> INDI ON_COORD_SET=TRACK
```

---

## Backend

### A. GoTo réel (#3)

**`MountService.goto_radec(ra_deg: float, dec_deg: float) -> None`** (nouvelle méthode du
Protocol, miroir de `sync_radec`).

`MountIndiAdapter.goto_radec` :
- Arme `ON_COORD_SET` sur le switch `TRACK` (1-of-many), puis écrit
  `EQUATORIAL_EOD_COORD` = `(RA en heures = ra_deg/15, DEC en degrés)` (JNow).
- Le driver Celestron exécute le slew **puis** enchaîne le tracking sidéral natif.
- No-op défensif si la propriété/le device est absent (cohérent avec `sync_radec`).
- `FakeMount.goto_radec` enregistre `(ra_deg, dec_deg)` dans `goto_calls` pour testabilité.

**Détection de fin de slew** : l'adapter écoute l'état de la propriété
`EQUATORIAL_EOD_COORD` via le hook de mise à jour INDI existant :
- À l'émission du goto : `bus.publish("mount", SubsystemState(state="moving",
  details={"goto": {"target_name", "ra_deg", "dec_deg"}, "goto_in_progress": True}))`.
- Sur la transition de la propriété `BUSY → OK/IDLE` : `state="ready"`,
  `goto_in_progress=False`, et `tracking` reflète `sidereal` (lecture
  `TELESCOPE_TRACK_STATE`).
- La progression n'est pas un pourcentage fiable : on expose `goto_in_progress`
  (booléen) ; l'app affiche une progression indéterminée.

**Router `POST /goto`** (nouveau, style miroir de `/align/*`) :
- Body Pydantic `GotoRequest { ra_deg: float, dec_deg: float, target_name: str | None }`.
- Garde : **409** si `is_aligned` est faux.
- **409** si un GoTo est déjà en cours (`goto_in_progress`) — l'utilisateur doit STOP
  d'abord (pas de remplacement de cible).
- **422** sur coordonnées invalides (validation Pydantic : dec ∈ [−90, 90], ra ∈ [0, 360)).

**Abort** : pas de nouvel endpoint. Le bouton STOP réutilise le `POST /stop` existant
(`stop_slew(axis=None)` → `TELESCOPE_ABORT_MOTION`).

### B. Flag `is_aligned`

- Vit **en mémoire** dans `AlignmentService` : `False` à la construction (process neuf),
  `True` après `finalize()`, `False` après `cancel()` et après `invalidate()`.
- **Invalidation sur reconnexion monture** : un abonné dans l'orchestrateur écoute les
  transitions du sous-système `mount` vers `disconnected`/`connecting` et appelle
  `alignment.invalidate()`. Couvre le cas d'un redémarrage indiserver-seul sous un backend
  resté debout. Le cas courant (coupure secteur → process FastAPI neuf) est déjà couvert
  par l'init en mémoire.
- Exposé dans l'état SSE du sous-système `alignment` : `details.is_aligned` (s'ajoute aux
  `rms`/`quality` déjà publiés à la finalisation).

### C. Visibilité « maintenant » (approche A)

**`astro_brain/services/_ephemeris.py`** (nouveau module pur) : on y **déplace**
`sky_az_alt_from_ra_dec`, `Observer`, `_gmst_deg`, `_julian_date` depuis
`_alignment_catalog.py`, qui les ré-importe (aucune duplication, aucun changement de
comportement de l'alignement). Module sans I/O, testable isolément.

**`VisibilityEnricher`** (couche au-dessus de `CatalogRegistry`) :
- Dépendances injectées : `observer() -> Observer | None` (lat/lon depuis l'état GPS) et
  `now_utc() -> datetime`.
- Pour chaque `CatalogObject`, calcule `altitude_deg`/`azimuth_deg` à l'instant courant.
- `CatalogObject` (Pydantic) gagne deux champs optionnels : `altitude_deg: float | None`,
  `azimuth_deg: float | None` (défaut `None`, n'impactent pas la table sqlite).

**`/catalog/objects`** : nouveau paramètre `visible_now: bool = False`.
- GPS fixé : enrichit alt/az ; si `visible_now`, filtre `altitude > 0°` (au-dessus de
  l'horizon géométrique). Le seuil pratique (obstruction/min-alt) viendra du Setup plus tard.
- **Sans fix GPS** : dégradation gracieuse — `altitude_deg`/`azimuth_deg` restent `None`,
  le filtre `visible_now` est ignoré (renvoie tout). Aucune erreur.

---

## Frontend — `lib/features/catalogue/`

Structure miroir du wizard d'alignement (meilleur précédent).

- **`catalogue_models.dart`** — `CatalogObjectDto` (miroir Pydantic : `qualifiedId`, `kind`,
  `name`, `designation`, `raDeg`, `decDeg`, `mag`, `constellation`, `objectType`,
  `altitudeDeg`, `azimuthDeg`) avec `fromJson`.
- **`catalogue_repository.dart`** — façade REST sur `ApiService` :
  `listObjects({String? search, double? maxMag, bool visibleNow})`,
  `goto(CatalogObjectDto obj)` (POST `/goto`), `abort()` (POST `/stop`).
- **`catalogue_bloc.dart`** :
  - Events : `CatalogueOpened`, `SearchChanged(text)` (debounce ~300 ms),
    `MagFilterChanged(maxMag?)`, `VisibleNowToggled(bool)`, `ObjectSelected(obj)`,
    `GoToRequested(obj)`, `AbortRequested`.
  - States (sealed) : `CatalogueLoading`, `CatalogueLoaded(objects, filters)`,
    `CatalogueError(message)`.
  - Le bloc ne gère que liste/filtre/sélection/déclenchement. Les statuts transverses
    (`is_aligned`, `goto_in_progress`, fix GPS) viennent de l'`AppBloc`/SSE.
- **`catalogue_screen.dart`** :
  - `AstroAppBar(current: AstroScreen.catalogue)`.
  - **Bandeau non-aligné** (BlocBuilder sur `AppBloc`) : visible si `!is_aligned`, lien
    « Lancer l'alignement → » qui pousse `AlignmentWizardScreen`.
  - Barre de recherche + chips (`VISIBLE MAINTENANT` — désactivée si pas de fix GPS,
    `MAG ≤ 3`, `MAG ≤ 2`).
  - `ListView` de **cartes** (nom, désignation·constellation, pill mag, pill ALT/AZ).
  - Tap carte → **bottom sheet** (`showModalBottomSheet`) : détails complets + bouton
    **POINTER (GOTO)** (grisé si `!is_aligned`, hint explicatif).
- **Slew bar** (overlay piloté par `AppBloc`, `mount.details.goto`) : nom de cible,
  progression indéterminée, bouton **STOP** → `AbortRequested`. Confirmation brève à
  l'arrivée (`goto_in_progress` repasse à faux).
- **Hub** : carte CATALOGUE (HugeIcons, hero icon astro) insérée dans `hub_screen.dart` ;
  `AstroScreen.catalogue` ajouté à l'enum de `AstroAppBar`.
- **Wiring `app.dart`** : `BlocProvider<CatalogueBloc>` (depuis `CatalogueRepository`).

### Pagination

Le catalogue actuel est petit (~140 étoiles, court après filtre visible-now). On charge en
une requête (`limit` couvrant le total). La pagination paresseuse est différée à Macro 4
(NGC/IC).

---

## Erreurs & cas limites

| Cas | Comportement |
|-----|--------------|
| Pas de fix GPS | Chip « visible maintenant » désactivée + hint ; liste complète sans alt/az |
| GoTo sans alignement | Bouton grisé (app) + 409 (backend) |
| GoTo pendant un slew | Refusé 409 ; l'utilisateur fait STOP d'abord |
| Offline | Bandeau global AppBloc déjà géré ; liste vide + reconnect |
| Coordonnées invalides | 422 (validation Pydantic) |

---

## Tests

**Backend**
- `goto_radec` adapter : arme `TRACK`, push RA en heures + DEC en degrés ; no-op si
  propriété/device absent ; `FakeMount.goto_calls`.
- Détection fin de slew : transition propriété `BUSY → OK` → `goto_in_progress` faux + ready.
- Garde `/goto` : 409 non-aligné, 409 slew en cours, 422 coords invalides, 200 nominal.
- `is_aligned` : faux à l'init, vrai après `finalize`, faux après `invalidate`/`cancel` ;
  abonné bus invalide sur transition mount `ready → disconnected`.
- `_ephemeris` : valeurs alt/az pour étoiles connues à date/observateur fixés (réutilise
  les cas existants de l'alignement, qui ne doivent pas régresser après le déplacement).
- `VisibilityEnricher` : enrichit alt/az ; filtre `visible_now` ; dégradation no-GPS.
- Routes catalogue : `visible_now` param, champs alt/az dans la réponse.

**Frontend**
- `CatalogueBloc` (bloc_test) : recherche debounce, filtres mag/visible, sélection, goto,
  abort, erreur.
- Widget tests (helper `_wrap`) : bandeau aligné vs non-aligné, bouton GoTo grisé/actif,
  ouverture bottom sheet, affichage slew bar piloté par état mount, chip visible-now
  désactivée sans GPS.

---

## Hors périmètre (différé)

- Tranches catalogue Messier + planètes (skyfield).
- Seuil de visibilité par obstruction/min-alt issu du Setup tube (Macro 4).
- Pagination paresseuse (Macro 4 NGC/IC).
- Validation matérielle E2E (slew réel) — bloquée dongle CP2102 (Macro 1).
- Tracking manuel post-GoTo, recentrage fin — couverts ailleurs.
