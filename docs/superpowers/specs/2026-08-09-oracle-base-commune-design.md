# Design — Oracle SP1 : `reference.sqlite` v2, base catalogue commune

Date : 2026-08-09
Statut : validé (brainstorm)
Fil : transverse « Oracle / Éphémères » (hors train de macros)
Sous-projet : **SP1 — Producteur** (prérequis de SP2 backend + SP3 app)
Références : genèse [`oracle-genese.md`](../../project/oracle-genese.md) · ADR [`2026-07-24`](../../project/decisions.md) · contrat [`oracle/README.md`](../../../oracle/README.md) · tranche 1 producteur [`2026-07-24-oracle-producer.md`](../plans/2026-07-24-oracle-producer.md)

## Objectif

Faire de `reference.sqlite` la **source de vérité unique du catalogue** — toutes
familles d'objets, une seule base, un seul artefact, consommé hors-ligne. SP1
étend le producteur `oracle/` (aujourd'hui : comètes seules) pour qu'il fabrique
cette base commune sous un **schéma unifié** versionné `schema_version = 2`.

SP1 ne touche **aucun** code consommateur (app/backend) : il fournit la donnée.
Le principe directeur, posé par l'utilisateur : **une seule source de données et
un seul code** — pas de catalogue dupliqué entre `state.db` et `reference.sqlite`,
pas de deux pipelines. La base reste **complète et tube-agnostique** : aucun
pré-filtre par magnitude/taille/type dans le producteur ; le filtrage « ce que
montre mon tube » est une décision **consommateur** (change avec l'optique).

## Décisions de conception (issues du brainstorm)

1. **Deux natures d'objets, un seul artefact.**
   - *Fixes* (RA/Dec quasi-statique) : deep-sky (Messier + NGC/IC) + étoiles →
     **une position par objet**.
   - *Éphémères* (se déplacent) : comètes + planètes + Lune + Soleil →
     **éphéméride pré-calculée** (samples journaliers, fenêtre glissante 60 j).
2. **Schéma unifié par nature** (voir DDL) : une table d'identité `objects`, une
   table `fixed_object`, une table `ephemeris` partagée comètes/planètes/luminaires,
   une table `comet_elements` pour les extras propres aux comètes. Zéro table
   d'éphéméride dupliquée.
3. **Deep-sky = OpenNGC, complet, sans pré-filtre.** Messier n'est **pas** une
   source séparée : c'est un sous-ensemble d'OpenNGC (colonne de cross-référence
   `M`). Une seule source deep-sky couvre Messier *et* NGC/IC (~13 000 objets,
   < 2 Mo en sqlite — négligeable).
4. **Étoiles = fetch IAU-CSN**, pas un set figé. Le *Catalog of Star Names* de
   l'IAU (`IAU-CSN.txt`, WGSN) est fetché au build comme les autres sources
   fetchables. `seed_stars.sql` (backend) est **retiré en SP2**, quand le backend
   bascule sur la lecture de l'artefact (pas en SP1, pour ne pas casser le backend
   entre-temps — seule entorse transitoire, assumée, à « une seule source »).
5. **Planètes = pré-calcul, pas de fetch.** Corps : Mercure, Vénus, Mars, Jupiter,
   Saturne, Uranus, Neptune, **Lune**, **Soleil**. **Pluton exclu** (mag ~14,
   hors de portée d'un 127 mm ; `de421` n'en donne que le barycentre). La source
   est le kernel **`de421.bsp`** déjà committé → 100 % déterministe, aucun réseau,
   aucun fallback nécessaire. Les consommateurs n'ayant **pas** de moteur
   d'éphéméride (genèse : « jamais de mécanique orbitale côté client » ; skyfield
   n'existe que dans `oracle/`), oracle est le **seul** endroit qui calcule — un
   seul code de calcul, des consommateurs muets.
6. **`kind` distingue `moon` et `sun` de `planet`.** La Lune porte une **phase**
   (`illumination`), le Soleil un **warning de sécurité au pointage** (filtre
   solaire obligatoire — l'utilisateur en possède un). Le Soleil est donc une
   **cible observable**, pas seulement un input crépuscule. (Le warning lui-même
   est une préoccupation consommateur SP2/SP3.)
7. **Le Soleil sert aussi la nuit astronomique.** Sa position échantillonnée
   permet au consommateur de calculer le crépuscule **hors-ligne** (il n'a pas
   skyfield) — support du critère de visibilité « au-dessus de l'horizon pendant
   la nuit ».
8. **Magnitude : colonne unique `apparent_mag`.** Fiable pour planètes/luminaires
   (via `planetary_magnitude` skyfield), estimation pour comètes. Le caveat
   « estimation, jamais un filtre dur » devient une **règle consommateur par
   `kind`** (kind = comet → afficher comme estimation), pas une colonne dédiée.
9. **Objets fixes stockés en RA/Dec of-date JNow à la génération** (skyfield
   projette depuis J2000). La dérive de précession entre deux builds hebdomadaires
   est négligeable. Cohérent avec la contrainte #5 de la genèse.
10. **Sampling journalier uniforme** pour tous les éphémères (une seule pipeline).
    Conséquence assumée : la Lune (~13°/j) subit ~0,1–0,5° d'erreur d'interpolation
    linéaire entre deux samples — négligeable pour la trouver (diamètre 0,5°) et
    pour le planning ; à noter seulement pour un GoTo lunaire ultra-précis.

## Sources

| Famille | `kind` | Source | Fetch | Fallback bundlé |
|---|---|---|---|---|
| Comètes | `comet` | MPC `CometEls.txt` | ✅ | ✅ (existant) |
| Deep-sky (Messier + NGC/IC) | `dso` | **OpenNGC** (CSV) | ✅ | ✅ (à committer) |
| Étoiles nommées | `star` | **IAU-CSN** (`IAU-CSN.txt`) | ✅ | ✅ (à committer) |
| Planètes | `planet` | kernel `de421.bsp` | ❌ | n/a |
| Lune | `moon` | kernel `de421.bsp` | ❌ | n/a |
| Soleil | `sun` | kernel `de421.bsp` | ❌ | n/a |

Les 3 sources fetchables partagent le patron déjà éprouvé pour les comètes :
fetch au build + snapshot bundlé versionné en fallback → **jamais de build cassé
faute de réseau**. Les planètes/luminaires sont le seul cas no-fetch.

## Le contrat : `reference.sqlite` v2 (DDL)

```sql
-- oracle/schema.sql (source de vérité du schéma ; meta.schema_version = 2)

CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,   -- 2 ; consommateur refuse si > version connue
  generated_at     TEXT    NOT NULL,   -- ISO-8601 UTC
  mpc_epoch        TEXT,               -- époque des éléments MPC (comètes)
  window_start     TEXT    NOT NULL,   -- début fenêtre éphéméride (UTC)
  window_end       TEXT    NOT NULL,   -- fin (UTC) ; ~60 j glissants
  skyfield_kernel  TEXT                -- "de421.bsp"
);

-- identité commune à TOUT objet du catalogue
CREATE TABLE objects (
  id           TEXT PRIMARY KEY,       -- id stable (packé MPC / "planet:mars" /
                                       --  "moon" / "sun" / "NGC1976" / "star:HIP24436")
  kind         TEXT NOT NULL,          -- comet | planet | moon | sun | dso | star
  name         TEXT,                   -- nom commun (nullable)
  designation  TEXT                    -- désignation catalogue (nullable)
);

-- objets fixes : une position + attributs statiques (deep-sky ET étoiles)
CREATE TABLE fixed_object (
  object_id     TEXT PRIMARY KEY REFERENCES objects(id),
  ra_deg        REAL NOT NULL,         -- of-date JNow à la génération
  dec_deg       REAL NOT NULL,
  apparent_mag  REAL,
  object_type   TEXT,                  -- galaxy / nebula / cluster / double-star / star / ...
  size_arcmin   REAL,                  -- taille apparente (nullable, ex. étoiles)
  constellation TEXT,
  messier       TEXT,                  -- "M42" si applicable (nullable)
  ngc_ic        TEXT                   -- "NGC1976" / "IC434" (nullable)
);

-- objets éphémères : samples pré-calculés (comètes + planètes + Lune + Soleil)
CREATE TABLE ephemeris (
  object_id     TEXT NOT NULL REFERENCES objects(id),
  sample_utc    TEXT NOT NULL,         -- pas journalier sur la fenêtre
  ra_deg        REAL NOT NULL,         -- of-date JNow
  dec_deg       REAL NOT NULL,
  earth_dist_au REAL,                  -- distance Terre (nullable pour le Soleil ? cf. note)
  sun_dist_au   REAL,                  -- distance Soleil (nullable)
  apparent_mag  REAL,                  -- fiable planètes/luminaires ; estimation comètes
  illumination  REAL,                  -- fraction éclairée 0..1 (Lune/Vénus/Mercure) ; NULL sinon
  constellation TEXT,
  PRIMARY KEY (object_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);

-- extras propres aux comètes (éléments orbitaux)
CREATE TABLE comet_elements (
  object_id          TEXT PRIMARY KEY REFERENCES objects(id),
  epoch_jd           REAL,
  perihelion_q_au    REAL NOT NULL,
  eccentricity       REAL NOT NULL,
  inclination_deg    REAL NOT NULL,
  arg_perihelion_deg REAL NOT NULL,
  node_deg           REAL NOT NULL,
  -- mag_h/mag_k = params de magnitude totale cométaire (g,k),
  -- m = g + 5*log10(delta) + 2.5*k*log10(r) ; PAS le système H,G des astéroïdes.
  mag_h              REAL,
  mag_k              REAL
);
```

Notes de contrat :
- **Restructuration des tables comètes existantes** : `comets` → `objects` (kind=
  `comet`) + `comet_elements` ; `comet_ephemeris` → `ephemeris`. Gratuit car
  **aucun consommateur ne lit encore l'artefact** (SP2/SP3 pas faits). Renommage
  `predicted_mag` → `apparent_mag`.
- **`earth_dist_au` / `sun_dist_au`** : passées `NOT NULL` → **nullable** dans le
  schéma unifié (le Soleil n'a pas de « distance au Soleil » ; garder des colonnes
  optionnelles évite un cas spécial). Les comètes/planètes les renseignent.
- **Familles futures** (hors SP1, pour cadrer) : `events`
  (conjonctions/oppositions/éclipses/showers), `appulses`. `schema_version`
  s'incrémentera à leur ajout.

## Pipeline de build

```
fetch (3 sources fetchables + fallback bundlé)
  ├─ MPC CometEls.txt   → comètes (existant)
  ├─ OpenNGC CSV        → deep-sky (Messier via cross-ref + NGC/IC)
  └─ IAU-CSN.txt        → étoiles nommées
skyfield
  ├─ FIXES : projeter deep-sky + étoiles (J2000 → of-date JNow) → fixed_object
  └─ ÉPHÉMÈRES : comètes (existant) + planètes/Lune/Soleil
        sur la fenêtre glissante 60 j, sample journalier
        → ephemeris (+ apparent_mag via planetary_magnitude, + illumination
          via fraction_illuminated, + constellation)
build_db (schéma v2)  → reference.sqlite
manifest              → manifest.json (schema_version=2, sha256, fenêtre)
```

Structure de code (extension de l'existant, pas de réécriture des acquis) :
- `oracle/oracle/sources/` : `comets.py` (existant), **`deep_sky.py`** (OpenNGC),
  **`stars.py`** (IAU-CSN) — chacun `fetch_* (+ fallback)` + `load_*`.
- `oracle/oracle/compute/` : `ephemeris.py` (existant, comètes) étendu ou
  complété par **`planets.py`** (planètes/Lune/Soleil depuis `de421`) + une
  projection **fixes** (J2000 → of-date) pour deep-sky/étoiles.
- `oracle/oracle/build_db.py` : réécrit pour le schéma unifié v2 (peuple `objects`,
  `fixed_object`, `ephemeris`, `comet_elements`).
- `oracle/data/` : `de421.bsp` (existant), `CometEls.fallback.txt` (existant),
  **`OpenNGC.fallback.csv`**, **`IAU-CSN.fallback.txt`** (snapshots à committer).

La CI `.github/workflows/oracle.yml` est inchangée dans sa mécanique (cron hebdo +
push `oracle/**` + dispatch) ; elle republie simplement l'artefact v2 sous
`almanac-latest`.

## Tests & contrat

- **TDD**, même discipline que la tranche producteur existante. Fixtures **offline**
  (kernel committé + snapshots fallback) → build **déterministe**, aucun réseau en
  test.
- Assertions par famille : chaque `kind` présent ; **Messier = 110** repérables
  dans le deep-sky ; **9 corps éphémères** (7 planètes + Lune + Soleil) ; N étoiles
  IAU-CSN ; NGC/IC non vide. Intégrité FK `fixed_object`/`ephemeris`/`comet_elements`
  → `objects`. `illumination` renseignée pour la Lune, NULL pour une comète.
  `schema_version = 2`. Positions of-date cohérentes (bornes RA 0–360, Dec ±90).
- `oracle/README.md` (le contrat consommateur) mis à jour pour le schéma v2.

## Hors périmètre SP1

Repoussé à SP2 (backend) / SP3 (app) :
- **sync / cache** de l'artefact côté consommateurs ;
- **projection alt/az** côté client + résolution GoTo ;
- **warning de sécurité solaire** au pointage ;
- **notifications** locales ;
- **suppression de `seed_stars.sql`** et bascule du backend sur la lecture de
  `reference.sqlite` (SP2).

SP1 s'arrête à : *publier un artefact v2 correct, complet, versionné et vérifiable.*
