# Design — Oracle / Éphémères, tranche 1 : infra `oracle/` + comètes

Date : 2026-07-24
Statut : validé (brainstorm)
Fil : transverse « Oracle / Éphémères » (hors train de macros)
Tranche : 1 — infrastructure du plan de référence + comètes
ADR fondateur : [2026-07-24 — Plan de données de référence indépendant du Pi + module `oracle/`](../../project/decisions.md)

## Objectif

Poser le **plan de données de référence autonome du Pi** et le livrer bout en bout sur le
premier cas utile : les **comètes observables**. À la fin de cette tranche, l'utilisateur
voit — **app connectée ou non, Pi éteint** — la liste des comètes actuellement pertinentes
pour sa position, et reçoit des notifications locales (« Comète TOTO visible ce mois-ci »).

C'est la tranche qui construit le socle réutilisé par les suivantes (événements calculés,
appulses) : module `oracle/`, contrat `reference.sqlite`, pipeline CI, mécanique de sync,
consommation côté app + Pi. Les comètes sont choisies comme ancre car elles sont le **seul
cas nécessitant un fetch de données fraîches** (les autres événements se calculent).

## Décisions de conception (issues du brainstorm / ADR)

1. **Trois plans de données, non conflatés** : live/contrôle (Pi), config/calibration
   (`state.db` Pi), **référence** (autonome). Cette tranche ne touche que la référence.
2. **Génération hors-Pi** : job **GitHub Actions** (skyfield + fetch MPC) → publie
   `reference.sqlite` + `manifest.json`. Aucune exécution sur le Pi, aucun serveur.
3. **Distribution = fichier caché localement**, pas de BDD interrogée en direct. App et Pi
   téléchargent le fichier (sync conditionnelle) et l'interrogent **hors ligne**.
4. **Calcul réparti** : le CI pré-calcule les échantillons **RA/Dec** + magnitude prédite ;
   les consommateurs font la **projection alt/az** (trigo simple, pas de mécanique orbitale
   côté client).
5. **Module `oracle/`** : pair de `backend/`/`app/` dans le monorepo, zéro dépendance vers
   eux, le **schéma SQLite est l'unique interface**.
6. **Notifs locales** (`flutter_local_notifications`) ; **FCM différé**.
7. **Périmètre observabilité tranche 1** : au-dessus de l'horizon pendant la nuit
   astronomique + magnitude prédite affichée. Le **seuil oculaire/photo** dépend du Setup
   tube (Macro 4) / caméras (Macro 5) → **différé**, hooks laissés.

## Architecture du module `oracle/`

```
ASTRO-BRAIN/
├── backend/           # consommateur (Pi)
├── app/               # consommateur (Flutter)
├── oracle/            # ← producteur (tourne en CI, jamais sur le Pi)
│   ├── pyproject.toml         # projet Python indépendant (uv), dep skyfield
│   ├── oracle/
│   │   ├── sources/comets.py  # fetch + parse MPC CometEls.txt
│   │   ├── compute/ephemeris.py  # skyfield : éléments → RA/Dec/dist/mag sur la fenêtre
│   │   ├── build_db.py         # écrit reference.sqlite (schéma versionné)
│   │   └── manifest.py         # génère manifest.json (version, dates, schema_version)
│   ├── schema.sql             # DDL du contrat — source de vérité du schéma
│   ├── tests/
│   └── README.md              # le contrat + la mécanique, pour les consommateurs
└── .github/workflows/oracle.yml   # cron + publication de l'artefact
```

## Le contrat : `reference.sqlite` (tranche 1)

Fichier SQLite indexé. `schema_version` entier dans `meta` gouverne la compat ascendante.

```sql
-- métadonnées de génération (une seule ligne)
CREATE TABLE meta (
  schema_version   INTEGER NOT NULL,   -- consommateurs : refus si > version connue
  generated_at     TEXT    NOT NULL,   -- ISO-8601 UTC
  mpc_epoch        TEXT,               -- date des éléments MPC utilisés
  window_start     TEXT    NOT NULL,   -- début de la fenêtre d'éphéméride (UTC)
  window_end       TEXT    NOT NULL,   -- fin (UTC) ; ~60 j glissants
  skyfield_kernel  TEXT                -- ex. "de421.bsp"
);

-- une comète (éléments orbitaux + identité + mag params)
CREATE TABLE comets (
  id            TEXT PRIMARY KEY,      -- désignation packée MPC (stable)
  designation   TEXT NOT NULL,         -- ex. "C/2023 A3"
  name          TEXT,                  -- ex. "Tsuchinshan-ATLAS" (peut être NULL)
  epoch_jd      REAL NOT NULL,
  perihelion_q_au   REAL NOT NULL,
  eccentricity      REAL NOT NULL,
  inclination_deg   REAL NOT NULL,
  arg_perihelion_deg REAL NOT NULL,
  node_deg          REAL NOT NULL,
  perihelion_time_jd REAL NOT NULL,
  mag_h         REAL,                  -- magnitude absolue (H)
  mag_k         REAL                   -- paramètre de pente (k / 2.5n)
);

-- échantillons pré-calculés (le "dur" fait par skyfield en CI)
CREATE TABLE comet_ephemeris (
  comet_id      TEXT NOT NULL REFERENCES comets(id),
  sample_utc    TEXT NOT NULL,         -- pas journalier sur la fenêtre
  ra_deg        REAL NOT NULL,         -- ICRS/JNow (à fixer, voir Questions ouvertes)
  dec_deg       REAL NOT NULL,
  earth_dist_au REAL NOT NULL,
  sun_dist_au   REAL NOT NULL,
  predicted_mag REAL,                  -- estimation (peu fiable — à afficher comme telle)
  constellation TEXT,
  PRIMARY KEY (comet_id, sample_utc)
);
CREATE INDEX idx_ephem_time ON comet_ephemeris(sample_utc);
```

Notes de contrat :
- **Le producteur ne connaît pas le site de l'utilisateur** → il ne stocke que du RA/Dec
  (indépendant du lieu). L'alt/az est projetée par le consommateur.
- La **magnitude prédite des comètes est notoirement peu fiable** (sursauts) → champ fourni
  mais **affiché comme estimation**, jamais comme vérité ; jamais utilisé comme filtre dur.
- Tables futures (hors tranche 1, mentionnées pour cadrer le schéma) : `events`
  (conjonctions/oppositions/éclipses/showers calculés), `appulses`. `schema_version`
  s'incrémente à leur ajout.

## Pipeline GitHub Actions (`.github/workflows/oracle.yml`)

- **Déclencheurs** : `schedule` (cron **hebdomadaire** — les comètes n'apparaissent pas à
  la journée, cf. ADR) + `workflow_dispatch` (manuel) + `push` sur `oracle/**` (régénère
  après un changement de code).
- **Étapes** : `uv sync` dans `oracle/` → `fetch` CometEls.txt (avec **fallback bundlé**
  versionné si MPC est down → jamais d'échec de build faute de réseau) → `skyfield` calcule
  la fenêtre glissante → `build_db.py` écrit `reference.sqlite` → `manifest.py` écrit
  `manifest.json`.
- **Publication** : en **asset de GitHub Release** sous un tag roulant `almanac-latest`
  (PAS de commit binaire quotidien dans `main` → zéro bloat d'historique git). Alternative
  équivalente : branche `gh-pages`. Les consommateurs tapent une URL stable.
- **`manifest.json`** (petit, sert de point de sync) :
  ```json
  { "schema_version": 1, "generated_at": "…", "sqlite_url": "…",
    "sqlite_sha256": "…", "window_start": "…", "window_end": "…" }
  ```
- **Coût** : job ~1–5 min, hebdo → quelques min/mois, dans le gratuit **par construction**
  (repo public illimité ; repo privé 2000 min/mois). Gotcha noté : cron désactivé après
  60 j d'inactivité repo (non-sujet en dev actif).

## Consommateurs

Les deux consomment le **même** `reference.sqlite` indépendamment.

### App Flutter (`lib/features/oracle/`, nom de dossier à confirmer)

- **Sync** : au lancement + pull-to-refresh, `GET manifest.json` ; si `generated_at` /
  `sqlite_sha256` diffère du cache local → télécharge `reference.sqlite` (quelques Mo) dans
  le stockage app. Sinon, no-op. **Fonctionne sur le dernier cache si hors ligne.**
- **Requêtes locales** : via `drift`/`sqflite`, sur le fichier caché.
- **Projection alt/az** : réutiliser la logique de projection (miroir Dart de
  `sky_az_alt_from_ra_dec`) à partir de RA/Dec échantillonné (interpolation linéaire entre
  deux samples journaliers) + position (site configuré / geolocator téléphone) + heure.
- **UI** : liste des comètes « pertinentes » (au-dessus de l'horizon pendant la nuit à
  venir depuis le site), détail (magnitude estimée, distances, fenêtre de visibilité,
  carte de position), tri par observabilité. Réutilise les conventions catalogue existant
  (cartes aérées, bottom sheet, `AstroAppBar`).
- **Lien session** : quand le Pi est là et la monture alignée, une comète peut alimenter un
  **GoTo** (le Pi résout son RA/Dec courant — voir Pi ci-dessous). Sinon, consultation pure.

### Pi (backend)

- **Sync** : au démarrage du service (si réseau) rafraîchit sa copie locale de
  `reference.sqlite` ; sinon utilise le cache. Copie **distincte** de `state.db`.
- **Usage** : résolution d'une cible comète pour le GoTo (RA/Dec à l'instant courant, par
  interpolation des samples) ; enrichissement de visibilité live via GPS déjà en place.
- **Pas de régression** : `state.db` (config/calibration) reste la BDD Pi-owned RW, jamais
  mélangée avec `reference.sqlite` (RO, jetable).

## Notifications (tranche 1 : local uniquement)

- À chaque sync réussie, l'app (re)programme des **notifications locales** depuis le bundle :
  - « Comète TOTO observable ce mois-ci » quand une comète entre dans une fenêtre
    d'observabilité future depuis le site configuré.
  - Récap mensuel « X objets sympas ce mois-ci » si plusieurs entrées pertinentes.
- Aucune dépendance réseau au moment du déclenchement (tout est local, prévu à l'avance).
- **FCM différé** : hook d'architecture laissé (le job Actions pourra pousser via l'API HTTP
  FCM), mais **hors périmètre tranche 1**.

## Flux

```
[GitHub Actions — hebdo]
   fetch MPC CometEls.txt (fallback bundlé) ─▶ skyfield (fenêtre 60j)
   ─▶ build reference.sqlite + manifest.json ─▶ Release asset "almanac-latest"
                         │ URL stable
        ┌────────────────┴─────────────────┐
        ▼ (sync conditionnelle manifest)     ▼ (sync conditionnelle manifest)
[App Flutter]                          [Pi backend]
  cache local + requêtes SQL             cache local + requêtes SQL
  projection alt/az (site+heure)         résolution GoTo comète (RA/Dec courant)
  notifs locales programmées             enrichissement visibilité live (GPS)
        │ (au télescope seulement) live/contrôle via REST+SSE ▲
        └───────────────────────────────────────────────────┘
```

## Tests

**`oracle/` (Python)**
- `sources/comets.py` : parse d'un `CometEls.txt` fixture (quelques comètes) → structures ;
  fallback si fetch échoue.
- `compute/ephemeris.py` : RA/Dec/dist pour une comète connue à une date fixée comparés à
  des valeurs de référence skyfield (tolérance) ; magnitude prédite calculée depuis H/k.
- `build_db.py` : génère un `reference.sqlite` conforme à `schema.sql` ; `meta` peuplée ;
  `comet_ephemeris` couvre la fenêtre au pas journalier ; intégrité des FK.
- `manifest.py` : `sqlite_sha256` correspond au fichier ; champs présents.

**App Flutter**
- Repository sync : manifest inchangé → pas de download ; changé → download ; hors ligne →
  cache conservé, aucune erreur.
- Projection alt/az : valeurs pour RA/Dec + site + heure fixés (miroir des cas backend).
- Bloc oracle : liste, tri par observabilité, sélection, (GoTo si aligné — réutilise le
  contrat `/goto` existant).
- Notifs : programmation depuis un bundle fixture (fenêtre future → notif planifiée).

**Backend (Pi)**
- Sync au boot avec/sans réseau (cache) ; résolution GoTo d'une comète (interpolation
  RA/Dec) ; `state.db` intacte et distincte.

## Hors périmètre (tranches / macros suivantes)

- **Événements calculés** (conjonctions, oppositions, éclipses, meteor showers) — tranche 2,
  100 % skyfield, même pipeline, table `events`.
- **Appulses** (« Jupiter devant une galaxie », planète ↔ comète) — tranche 3, combinatoire,
  balayage grossier-puis-fin.
- **Discriminant oculaire vs photo** : seuil visuel (diamètre + brillance de surface) avec
  *Setup tube* (Macro 4) ; seuil photo (tube + caméra) avec *Setup caméras* (Macro 5).
- **FCM / push temps réel** — si le besoin « transitoire ce soir, n'importe où » se confirme.
- **Astéroïdes géocroiseurs, alertes novæ/supernovæ** (TNS/AAVSO) — au-delà, sur le même
  socle.
- **Fusion du catalogue statique** (Messier/NGC/IC) dans `reference.sqlite` pour un catalogue
  offline complet côté app — à arbitrer quand Macro 4 densifie le catalogue.

## Questions ouvertes (à trancher en plan d'implémentation)

1. **Repère RA/Dec** stocké : ICRS/J2000 (stable, projection JNow côté client) vs JNow
   pré-calculé (aligné sur `EQUATORIAL_EOD_COORD` du GoTo). Impacte la projection et le GoTo.
2. **Pas d'échantillonnage** : journalier suffit-il pour une comète rapide près du périhélie,
   ou pas adaptatif ? (interpolation linéaire acceptable ?)
3. **Site pour les notifs** : site d'observation configuré explicitement (nouvelle petite
   config app) vs dernière position geolocator connue.
4. **Nom du dossier de feature Flutter** et emplacement de la logique de projection partagée.
