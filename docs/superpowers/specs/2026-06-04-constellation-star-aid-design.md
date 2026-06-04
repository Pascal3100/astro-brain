# Aide « voir l'étoile dans sa constellation » — Design

**Date** : 2026-06-04
**Macro** : 3 (Mise en station + GoTo basique), aide au wizard d'alignement (#2)
**Statut** : design validé, à implémenter

## Objectif

Aider l'utilisateur à reconnaître **quelle étoile choisir/centrer** pendant la
calibration GoTo, sans connaître les constellations ni les noms d'étoiles par
cœur. On affiche un **schéma au trait** de la constellation avec l'étoile cible
mise en évidence, orienté comme le ciel réel à l'instant T.

L'aide est **purement assistante** : elle ne change pas le flux du wizard 3
étoiles ([`2026-05-09-wizard-3star-alignment-design.md`](2026-05-09-wizard-3star-alignment-design.md)),
qui conserve ses 3 candidates auto-suggérées.

## Décisions clés

1. **Périmètre** : uniquement le wizard de calibration GoTo. Pas le catalogue
   utilisateur, pas de rendu réaliste de champ stellaire — **schéma au trait**
   (points dimensionnés par magnitude + lignes de figure).
2. **Deux points d'entrée, un seul widget** :
   - Écran par-étoile : nom de constellation dans le hero + bouton « voir dans
     la constellation » → **bottom sheet** avec le schéma (cohérent avec la
     fiche détail du catalogue).
   - Swap : ouvre un **écran-navigateur** (filtre par constellation + liste
     d'étoiles + même schéma).
   - Le composant de dessin `ConstellationChart` est partagé.
3. **Orientation** : le schéma est orienté **comme le ciel réel** (haut =
   zénith) via l'alt/az courant de chaque nœud. Badge « N↑ orienté ciel ».
   Quasi gratuit car on porte déjà le RA/Dec de chaque nœud et la conversion
   réutilise `_ephemeris.sky_az_alt_from_ra_dec`.
4. **Donnée des figures = asset autonome** : un jeu dédié, indépendant du
   catalogue go-to, pour ne pas le polluer avec des étoiles de figure mag 3-4.
5. **Position de l'observateur — chaîne de priorité** : fix GPS Pi (M8N) →
   sinon position du téléphone (permission Android) → sinon le wizard n'est pas
   proposé. **Suppression du fallback Paris codé en dur.**

## Contexte — état du code (vérifié 2026-06-04)

- `catalog_objects` contient 140 étoiles (mag ≤ 3) sur 39 constellations, avec
  `ra_deg/dec_deg/constellation`. **Aucune donnée de connectivité de tracé**
  nulle part dans le repo. Le seuil mag ≤ 3 est trop sévère pour dessiner les
  figures (ex. Grande Ourse : 6/7 étoiles, **Megrez mag 3.31 manque**).
- Le wizard d'alignement a son propre catalogue `_alignment_stars.json` : **32
  étoiles**, champs `id/name/bayer/ra_deg/dec_deg/mag`. La **constellation est
  dérivable du champ `bayer`** (« α CMa » → `CMa`) — pas besoin d'un nouveau
  champ.
- `select_candidates` (`_alignment_catalog.py`) filtre déjà `alt > 20°` + courses
  monture à la position de l'observateur : le sélecteur auto est **sain dans son
  principe**. Le bug de « constellations non visibles » observé est dans le
  **menu déroulant client-side de la page catalogue** (indépendant de
  `visible_now`) → hors scope, backlog.
- **Faiblesse trouvée** (`app.py:92`) : sans fix GPS, l'observateur retombe sur
  `_DEFAULT_LAT/LON = Paris (48.8566, 2.3522)`. Sans fix et loin de Paris, le
  sélecteur calcule la visibilité pour Paris → candidates fausses. C'est la
  cause réelle de l'impact sur le sélecteur. La décision 5 corrige ça.

## Architecture

### Vue d'ensemble

```
Écran par-étoile ──[bouton "voir dans la constellation"]──▶ bottom sheet ┐
                                                                          ├─▶ ConstellationChart
Écran navigateur (swap) ──[filtre constellation + tap étoile]─────────────┘
        ▲
        └── GET /align/stars/visible (étoiles pointables, groupées par constellation)
            GET /align/constellation/{abbr}?target_hr=… (figure + alt/az par nœud)
```

### Donnée des figures

Fichier embarqué `backend/astro_brain/data/constellation_figures.json` :

```json
{
  "UMa": {
    "name": "Grande Ourse",
    "nodes": [
      {"hr": 4301, "label": "Dubhe",  "ra_deg": 165.932, "dec_deg": 61.751, "mag": 1.79},
      {"hr": 4295, "label": "Merak",  "ra_deg": 165.460, "dec_deg": 56.382, "mag": 2.37},
      {"hr": 4554, "label": "Megrez", "ra_deg": 183.857, "dec_deg": 57.033, "mag": 3.31}
    ],
    "segments": [[0, 1], [1, 2]]
  }
}
```

- **Nœud** : `hr` (n° Yale Bright Star, sert à matcher l'étoile cible),
  `label` (nom/Bayer), `ra_deg`, `dec_deg`, `mag`.
- **Segment** : paire d'index dans `nodes`.
- **Périmètre** : les constellations représentées parmi les 32 étoiles
  d'alignement (dérivées du champ `bayer`) — ~25-30 figures. Pas les 88, pas les
  39 du catalogue.
- **Construit une fois** par un script versionné (`backend/scripts/build_constellation_figures.py`),
  à partir de sources publiques : tracés type Stellarium `constellationship` +
  Yale Bright Star Catalogue pour résoudre HR → RA/Dec/mag/label. Le script ne
  tourne **pas** au runtime ; seul le JSON produit est embarqué.

### Backend

```
backend/astro_brain/services/
├── _alignment_catalog.py   # + constellation_of(star) dérivée du bayer
├── constellation_figures.py  # load asset + figure_for(abbr) + matching target_hr
backend/astro_brain/routes/alignment.py   # + 2 routes (voir API)
backend/astro_brain/data/constellation_figures.json   # asset embarqué
backend/scripts/build_constellation_figures.py         # build one-shot, hors runtime
```

API additionnelle :

| Verbe | Route | Description |
|---|---|---|
| `GET` | `/align/stars/visible` | Étoiles d'alignement actuellement pointables (alt > min_alt + courses), groupées par constellation. Mutualise la logique de `select_candidates`. |
| `GET` | `/align/constellation/{abbr}?target_hr=…` | Figure d'une constellation : nœuds (avec alt/az courants) + segments + `is_target` posé sur le nœud du `target_hr`. |
| `POST` | `/align/swap/{idx}` *(étendu)* | Accepte un `star_id` explicite (choix depuis le navigateur), en plus du comportement « next best » existant. |

Réponse `/align/constellation/{abbr}` :

```json
{
  "abbr": "UMa",
  "name": "Grande Ourse",
  "oriented": true,
  "nodes": [
    {"hr": 4301, "label": "Dubhe", "mag": 1.79, "ra_deg": 165.932, "dec_deg": 61.751,
     "az": 312.4, "alt": 47.1, "is_target": true}
  ],
  "segments": [[0, 1], [1, 2]]
}
```

- `alt/az` par nœud calculés à l'instant T à la position de l'observateur
  (chaîne de priorité, décision 5) via `sky_az_alt_from_ra_dec`. C'est ce qui
  permet l'orientation ciel.
- `oriented: false` si on n'a pas de position (cas dégradé) → l'app projette
  depuis RA/Dec sans badge « orienté ciel ». En pratique ce cas ne se présente
  pas dans le wizard car sans position le wizard n'est pas proposé (décision 5) ;
  `oriented: false` reste un repli défensif de l'endpoint.

### Position de l'observateur

- **Suppression** de `_DEFAULT_LAT/_DEFAULT_LON` (Paris) dans `app.py`.
- `observer()` résout dans l'ordre : `sensors.gps_fix()` → position client
  poussée par le téléphone → `None`.
- **Repli téléphone** : l'app Flutter demande la localisation Android
  (permission + package `geolocator`) et la pousse au backend. Endpoint
  `POST /location/client { lat, lon }` (ou champ optionnel sur `/align/start`) ;
  stockée en RAM avec sa source.
- **Aucune position → pas de wizard** : `/align/start` refuse (409
  « position requise »). L'entrée « Aligner » du Hub passe en état prérequis
  (même pattern que le bandeau non-aligné du catalogue).
- **Persistance modèle** : on stocke la position effectivement utilisée + sa
  source (`pi_gps` / `phone`). Le restore (`ΔGPS < 20m`, cf. spec wizard) compare
  à la position courante quelle que soit la source.

### Frontend

```
app/lib/features/alignment/
├── widgets/constellation_chart.dart   # CustomPaint partagé
├── screens/star_navigator_screen.dart # swap : filtre constellation + liste + chart
└── (per_star_screen.dart)             # + hero constellation + bouton + bottom sheet
app/lib/features/alignment/repository/alignment_repository.dart
    # + fetchConstellation(abbr, targetHr) / fetchVisibleStars()
```

- `ConstellationChart` (CustomPaint) : projette chaque nœud `(az, alt) → (x, y)`
  avec **haut = zénith** ; sinon projection RA/Dec. Dots dimensionnés par
  magnitude, segments au trait, étoile cible en halo + label. Palette jour/nuit.
- Bottom sheet sur `per_star_screen` (déclenché par le bouton).
- `StarNavigatorScreen` : menu déroulant des **constellations visibles** (issues
  de `/align/stars/visible`, pas du filtre client-side du catalogue), liste
  d'étoiles, tap → chart, sélection → `swap` avec `star_id`.
- Hub : carte alignement avec état prérequis « Position requise » quand ni fix
  Pi ni position téléphone.

## Data flow

1. **Entrée wizard** : si pas de position (Pi ni téléphone), l'app tente la
   localisation téléphone (permission). Si refus/échec → Hub affiche « Position
   requise », `/align/start` reste bloqué (409).
2. **Par-étoile** : le hero affiche la constellation (dérivée du `bayer`). Tap
   « voir dans la constellation » → `GET /align/constellation/{abbr}?target_hr=…`
   → bottom sheet `ConstellationChart`.
3. **Swap** → `StarNavigatorScreen`. `GET /align/stars/visible` peuple le filtre
   et la liste. Tap étoile → chart. Sélection → `POST /align/swap/{idx} {star_id}`
   → retour à l'écran par-étoile avec la nouvelle candidate.

## Error handling

| Cas | Réponse |
|---|---|
| Ni fix Pi ni position téléphone | Wizard non proposé ; Hub « Position requise » ; `/align/start` → 409. |
| Permission localisation refusée | Pas de repli téléphone ; comportement « pas de position ». |
| `target_hr` absent de la figure | Figure renvoyée sans `is_target` ; chart dessine sans halo (log warning). |
| Constellation hors asset | `/align/constellation` → 404 ; le bouton « voir dans la constellation » n'est pas proposé pour cette étoile (le hero garde juste le nom). |
| Étoile cible hors de tout tracé (étoile isolée) | Pas de bouton « voir dans la constellation » ; aide indisponible pour cette étoile, le reste du wizard est intact. |

## Testing

### Backend (pytest)

- `test_constellation_figures.py` : intégrité de l'asset (chaque index de
  segment pointe un nœud existant ; chaque constellation des 32 étoiles
  d'alignement a une figure) ; `figure_for(abbr)` ; matching `target_hr` →
  `is_target`.
- `test_alignment_catalog.py` : `constellation_of(star)` dérive correctement
  l'abréviation du `bayer` (« α CMa » → `CMa`, casses limites).
- `test_alignment_router.py` : `/align/constellation/{abbr}` (connue → 200 avec
  `is_target` sur le bon HR ; inconnue → 404 ; `oriented` selon position) ;
  `/align/stars/visible` (groupe par constellation, ne renvoie que les
  pointables) ; `/align/swap/{idx}` avec `star_id` explicite ; `/align/start`
  → 409 sans position.
- Orientation : un nœud placé au zénith de l'observateur projette en haut du
  repère.
- Régression : `observer()` sans position renvoie `None` (plus de Paris).

### Frontend (flutter test)

- `constellation_chart_test.dart` : rend depuis un fixture (n nœuds + segments,
  cible en évidence) ; bascule orienté/atlas ; palette jour/nuit.
- `star_navigator_screen_test.dart` : filtre alimenté par les constellations
  visibles, tap étoile affiche le chart, sélection émet le bon event de swap.
- `per_star_screen_test.dart` (complément) : bouton « voir dans la
  constellation » ouvre le bottom sheet ; absent si étoile hors tracé.
- Hub : état prérequis « Position requise ».

### Intégration manuelle (post-dongle CP2102)

1. Wizard avec fix GPS Pi : hero affiche la bonne constellation, schéma orienté
   cohérent avec le ciel.
2. Sans fix Pi mais position téléphone accordée : wizard fonctionne.
3. Sans aucune position : wizard non proposé, Hub « Position requise ».
4. Swap → navigateur ne liste que des constellations réellement visibles.

## Hors scope

- **Bug du menu déroulant catalogue** (client-side, page catalogue Macro 3 #3)
  → backlog séparé. Cette spec ne touche pas la page catalogue.
- Figures pour le catalogue utilisateur.
- Rendu réaliste de champ stellaire.
- Seuil de visibilité « pratique » (obstruction / min-alt tube) — reste lié au
  Setup tube (Macro 4), cf. backlog.

## Références

- Spec wizard : [`2026-05-09-wizard-3star-alignment-design.md`](2026-05-09-wizard-3star-alignment-design.md)
- Maquettes : `.superpowers/brainstorm/33471-1780572318/content/` (`concept-v1.html`, `reveal-ab.html`)
- Éphéméride : `backend/astro_brain/services/_ephemeris.py`
- Sélecteur : `backend/astro_brain/services/_alignment_catalog.py`
- Étoiles d'alignement : `backend/astro_brain/services/_alignment_stars.json`
- Design system : `docs/product/design-system.md`
- Roadmap : `docs/project/roadmap.md` (Macro 3 #2)
