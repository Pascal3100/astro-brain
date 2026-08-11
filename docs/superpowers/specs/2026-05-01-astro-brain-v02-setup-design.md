# Spec — v0.2 Setup

> Date : 2026-05-01
> Statut : design validé, prêt pour writing-plans
> Précédente : [v0.1 design](archive/2026-04-16-astro-brain-v01-design.md) (manuel + tracking)
> ADR pivot scope : [decisions.md — Setup devient v0.2](../../project/decisions.md)

## Contexte

v0.1 a livré le contrôle manuel (joystick D-Pad + tracking sidéral) avec l'app Flutter native sur téléphone. La suite naturelle voulait être **mise en station 3 étoiles + GoTo + catalogue minimal** (v0.2 originale). En détaillant les prérequis, constat : impossible d'aligner sérieusement sans **calibration capteurs** (compass LIS3MDL, ADXL345 ×2), **courses ALT** (anti-collision tube ↔ monture), **backlash compensation** (tracking + GoTo précis).

D'où le pivot : **v0.2 = Setup**, mise en station + GoTo + catalogue passent en v0.3.

Critère de livraison v0.2 : **la monture est prête à être alignée proprement** — tous les capteurs calibrés, courses définies, backlash réglé monture-side, cordwrap protégé. À la fin de v0.2, l'utilisateur peut encore faire ce que v0.1 permettait, plus une page Setup avec 8 entrées de configuration persistantes.

## Scope

9 entrées dans la page Setup (correspondance 1:1 avec les cartes UI) :

| # | Item | Lieu de persistance |
|---|---|---|
| 1 | Niveau monture (calibration ADXL345 monture, bias 3D) | SQLite Pi |
| 2 | Compass (calibration LIS3MDL, soft-iron offsets) | SQLite Pi |
| 3 | Zéro ALT (calibration ADXL345 tube, bias 3D + zéro horizontal) | SQLite Pi |
| 4 | Courses ALT min/max | SQLite Pi |
| 5 | Backlash ALT pos/neg (0-99) | Monture (AUX), via passe-plat |
| 6 | Backlash AZ pos/neg (0-99) | Monture (AUX), via passe-plat |
| 7 | Cordwrap AZ (toggle + position de référence) | Monture (AUX), via passe-plat |
| 8 | Réseau (override host/port app) | shared_preferences côté app |
| 9 | À propos (versions, IP, SSID, uptime) | Lecture live |

**Hors scope explicite** :
- Mode hotspot Pi (NetworkManager / hostapd) — passe au backlog ; trop de glue côté OS pour la valeur en v0.2.
- `POST /system/restart` — l'utilisateur peut SSH ou redémarrer le Pi physiquement.
- Override host/port côté app — déjà géré v0.1 via `--dart-define`. v0.2 ajoute un écran de saisie qui persiste via `shared_preferences` côté app, sans toucher la DB Pi.
- Custom slew rates / PEC (existent dans le protocole NexStar mais sans valeur immédiate).

## Décisions structurantes

### Trois surfaces distinctes

1. **Bus système** (v0.1, **inchangé**) : pastille `overall` calculée sur 5 subsystems de santé sparse latch-y (mount, gps, tracking, network, system). Aucun nouveau subsystem en v0.2.
2. **Calibration sessions** (REST + SSE court-vivant) : une session par capteur, le Pi échantillonne lui-même I2C, l'app suit la progression.
3. **Live sensor streams** (SSE dédiés ouverts à la demande) : `/sensors/tilt/stream` et `/sensors/compass/stream`, fermés tant qu'aucun écran ne les consomme. Throttle 5 Hz pendant calibration ou alignement, sinon fermé.

Les états de configuration (calibration done/undone, valeurs backlash courantes) sont **lus à la demande via REST** — pas diffusés sur le SSE global.

### Persistance SQLite

DB à `/var/lib/astro-brain/state.db`, créé via `StateDirectory=astro-brain` dans le service systemd (perms auto). Accès async via `aiosqlite`. Schéma versionné par migrations Python ordonnées.

Tables v0.2 :

```sql
schema_version (version INTEGER PK, applied_at TEXT)

calibration_sensor (
  sensor_id   TEXT PK,           -- 'lis3mdl', 'adxl345_mount', 'adxl345_tube'
  payload_json TEXT NOT NULL,    -- offsets propres au capteur
  calibrated_at TEXT NOT NULL    -- ISO 8601 UTC
)

mount_limits (
  axis     TEXT PK,              -- 'alt' (un seul axe en v0.2)
  min_deg  REAL NOT NULL,
  max_deg  REAL NOT NULL,
  set_at   TEXT NOT NULL
)
```

**Pas de cache pour les valeurs monture** : backlash/cordwrap = lecture AUX à la demande, monture = autorité unique. La latence USB-série est ~50 ms, suffisante pour un GET.

### Lib NexStar

Décision déférée au plan d'implémentation v0.2. `nexstarpy` 0.1.0 ne wrappe ni le sync (`S`/`s`), ni l'AUX (backlash/cordwrap/MC_*) — toutes nécessaires. Au début du plan d'implé :

1. Chercher une lib Python plus complète (INDI/INDIGO bindings, ASCOM-like, forks community).
2. Si rien de mature : **fork interne** dans `backend/astro_brain/adapters/nexstar/`, ne dépend plus de `nexstarpy` upstream. Garder l'interface `MountAdapter` Protocol existante pour ne rien casser dans le reste du backend.

Référence complète du protocole : [`docs/technical/nexstar-protocol-reference.md`](../../technical/nexstar-protocol-reference.md). Inventaire ce que nexstarpy wrappe : [`docs/technical/nexstar-capabilities.md`](../../technical/nexstar-capabilities.md).

## Architecture backend

```
backend/astro_brain/
├── adapters/
│   ├── lis3mdl_adapter.py          # I2C 0x1E, raw mag readings
│   ├── adxl345_adapter.py          # I2C, 2 instances (0x53 tube, 0x1D mount)
│   └── nexstar_adapter.py          # étendu : *_backlash, *_cordwrap, sync (préparé v0.3)
├── services/
│   └── calibration.py              # orchestrateur sessions ; state machine ; sampling I2C
├── repository/
│   └── state_db.py                 # aiosqlite : sensors offsets, mount_limits ; migrations
├── routers/
│   ├── calibration.py              # /calibration/*
│   ├── limits.py                   # /limits/alt
│   ├── mount_tuning.py             # /mount/tuning (passe-plat AUX, pas de cache)
│   ├── sensors.py                  # /sensors/*/stream (SSE dédiés)
│   └── about.py                    # GET /about uniquement
└── models/
    └── calibration.py              # Pydantic : LIS3MDLOffsets, ADXL345Offsets, AltLimits, etc.
```

`calibration.py` (service) est le seul nouveau "service" justifié — il a un cycle de vie (start/sampling/computing/done|aborted), du throttling, et de l'orchestration entre adapter I2C, repository et routeur SSE. Le reste = routers + repository + adapters, sans couche service intermédiaire artificielle.

## API additions

### Calibration sessions

State machine côté service :

```
idle ─start→ sampling ─enough_samples→ computing ─ok→ done
                │                          │
                ├── /sample (Pi-driven)    └── error → idle
                └── /abort → idle
```

Endpoints :
```
POST /calibration/{sensor_id}/start     → 202 + session_id ; ouvre stream
GET  /calibration/{sensor_id}/stream    → SSE : { state, coverage_pct, sigma, samples_n, hint, residual? }
POST /calibration/{sensor_id}/finalize  → 200 + offsets calculés ; écrit DB ; ferme stream
POST /calibration/{sensor_id}/abort     → 200 ; ferme stream
GET  /calibration/{sensor_id}           → 200 + offsets persistés + calibrated_at, ou 404 si jamais calibré
```

`sensor_id ∈ {lis3mdl, adxl345_mount, adxl345_tube}`.

Une seule session active à la fois (renvoyer 409 si tentative de start alors qu'une session est en cours).

### Limits
```
GET  /limits/alt    → { min_deg, max_deg, set_at } | 404
PUT  /limits/alt    body: { min_deg, max_deg }    → 200
```

Le clamp s'applique côté backend dans `nexstar_adapter.slew_*` et `goto_*` ; toute commande qui viserait hors-bornes est tronquée + warning loggué.

### Mount tuning (passe-plat AUX)
```
GET  /mount/tuning                       → { backlash: { alt: {pos, neg}, az: {pos, neg} },
                                             cordwrap: { enabled, position_deg } }
PUT  /mount/tuning/backlash/{axis}       body: { pos: 0..99, neg: 0..99 }   → 200
PUT  /mount/tuning/cordwrap              body: { enabled, position_deg? }    → 200
```

Toutes ces routes lisent/écrivent la monture via AUX. Pas de DB. Si la monture est `mount=error`, retourner 503.

### Sensor live streams
```
GET  /sensors/tilt/stream     → SSE : { ts, pitch_deg, roll_deg, magnitude_g }
GET  /sensors/compass/stream  → SSE : { ts, heading_deg, magnitude_uT, raw: {x, y, z} }
```

Lazy-open : tant qu'aucun client n'écoute, le adapter ne pomp pas l'I2C. Throttle 5 Hz par défaut, configurable via query param `?hz=1..10`.

### About
```
GET /about → {
  backend_version, app_version_seen?, mount_firmware?,
  ip, ssid, uptime_s, started_at
}
```

## Frontend Flutter

### Routing

Splash → HomeScreen (v0.1 inchangée). Depuis HomeScreen, point d'entrée Setup **(option iii)** :

1. **Icône engrenage dans la AppBar partagée** — entre la pastille `overall` et le toggle thème. Tap → `/setup` (page liste).
2. **Bouton "Calibrer" contextuel** sur les cartes SystemScreen quand le subsystem signale un défaut imputable à une calibration manquante (uniquement à partir de v0.3 quand l'alignement consommera les calibrations ; en v0.2 les capteurs ne sont pas dans le bus santé donc ce point est dormant).

En v0.2, **seul le point 1 est actif** ; le point 2 sera implémenté en v0.3 quand le bus santé inclura `alignment` + signal "compass uncalibrated" pertinent.

### SetupScreen (page liste)

```
SetupScreen
├── AppBar partagée (status + setup icon désactivée puisqu'on y est + theme + reconnect)
├── titre "SETUP"
└── ListView de SetupCard (ordre numéroté)
    ├── 1. Niveau monture
    ├── 2. Compass
    ├── 3. Zéro ALT
    ├── 4. Courses ALT          ⚠ recommandé après 3
    ├── 5. Backlash ALT
    ├── 6. Backlash AZ
    ├── 7. Cordwrap AZ
    ├── 8. Réseau (override host/port app)
    └── 9. À propos
```

Convention C : ordre numéroté + warnings ⚠ jaunes pour les dépendances recommandées, **sans blocage dur**. L'utilisateur expert peut court-circuiter en connaissance de cause.

`SetupCard` : icône Phosphor + libellé + sous-libellé contextuel ("Calibré il y a 3j" / "Non calibré" / "Réglé sur monture") + pastille (gris/vert/jaune/rouge) + tap → sous-écran.

### Sous-écrans

Un par item, navigation push/pop standard. AppBar partagée préservée. Pattern bloc : `SetupBloc` racine (statut global Setup + persistance dépendances) + un bloc dédié par sous-écran (`Lis3mdlCalibrationBloc`, `Adxl345CalibrationBloc`, `LimitsBloc`, `BacklashBloc`, `CordwrapBloc`, `NetworkBloc`, `AboutBloc`).

### Live streams côté app

Deux services dédiés, similaires à `EventStreamService` v0.1 mais paramétrés :
- `TiltStreamService` — abonnement à `/sensors/tilt/stream` ; broadcast `Stream<TiltReading>`. Ouvert quand un écran l'expose, fermé à la sortie.
- `CompassStreamService` — idem pour `/sensors/compass/stream`.

Reconnexion auto, distinction `stop()` / `dispose()` (pattern v0.1).

## Flows par calibration

Conventions communes :
- Le Pi pilote l'échantillonnage I2C ; l'app n'envoie pas de samples.
- Pendant une session : SSE diffuse `{ state, coverage_pct, sigma, samples_n, hint }`.
- Le bouton "VALIDER" reste grisé tant que les seuils ne sont pas atteints.
- Annulation possible à tout moment via `/abort`.

### 1. Niveau monture (ADXL345 monture)

- **Geste** : poser la monture sur trépied, niveler physiquement avec une bulle (intégrée trépied ou clipsable). Maintenir immobile.
- **Sampling Pi** : ~100 lectures à 50 Hz (~2 s) par axe x/y/z.
- **Calcul** : moyenne 3D = bias. Variance σ doit être < 0.05 g pour valider.
- **Validation** : auto si σ < seuil et coverage suffisante (durée minimum atteinte).
- **Persistance** : `calibration_sensor[adxl345_mount].payload_json = { bias: [bx, by, bz], sigma: σ_final }`.

### 2. Compass (LIS3MDL)

- **Geste** : tourner le module dans 3 plans (figure 8 + rotations sphériques). Affichage 3D dome qui se remplit au fur et à mesure que les samples couvrent la sphère unitaire.
- **Sampling Pi** : continu pendant la session, throttle 50 Hz, accumulation jusqu'à 500-1000 samples ou interruption user.
- **Calcul** : fit ellipsoïde (algo Li-Lawley ou similaire) → centre = soft-iron offsets + matrice scale (hard-iron correction).
- **Validation** : couverture sphérique > 80% (mesurée par discrétisation en quadrants 3D) + résidu fit < seuil.
- **Persistance** : `calibration_sensor[lis3mdl].payload_json = { offsets: [bx, by, bz], scale_matrix: [[...], [...], [...]], coverage_pct, residual }`.

### 3. Zéro ALT (ADXL345 tube)

- **Geste** : tube horizontal — référence visuelle (bulle clipsable sur tube ou ligne d'horizon visible). Maintenir.
- **Sampling Pi** : idem ADXL345 monture.
- **Calcul** : bias 3D + angle ALT de référence (tube = 0° à cette position).
- **Validation** : σ < seuil.
- **Persistance** : `calibration_sensor[adxl345_tube].payload_json = { bias: [bx, by, bz], zero_alt_deg: 0.0, sigma: σ_final }`.

### 4. Courses ALT min/max

- **Geste** : "Pointer le tube le plus bas" → valider ; "Pointer le plus haut" → valider. L'app affiche en live l'angle ALT lu via ADXL345 tube (stream `/sensors/tilt/stream`).
- **Calcul** : 2 angles capturés côté backend.
- **Validation** : `min < max` et écart > 30° (sinon probable erreur user).
- **Persistance** : `mount_limits[alt] = { min_deg, max_deg }`.

### 5-6. Backlash ALT et AZ

UX la moins évidente — détaillée au plan d'implé. Squelette :

- **Geste** : pointer une cible terrestre fixe et bien définie (lampadaire de jour, par exemple). L'app slew dans une direction puis inverse par incréments. À chaque incrément, demande "vois-tu bouger ?". L'utilisateur clique "oui" quand le mouvement est observé.
- **Calcul** : nombre d'incréments avant mouvement perçu × valeur d'incrément → valeur AUX 0-99.
- **Mesures** : 4 mesures par axe (pos puis neg en ALT, pos puis neg en AZ). Moyennes pour stabiliser.
- **Validation** : valeurs cohérentes (pos ≈ neg ± marge), sinon proposer reprise.
- **Persistance** : `PUT /mount/tuning/backlash/{axis}` push direct AUX. Pas de DB.

### 7. Cordwrap AZ

- **Geste** : "Vérifiez que le câble est arrangé pour permettre un tour complet sans toucher d'obstacle." Bouton "Position de référence". Toggle "Activer cordwrap".
- **Calcul** : aucun (juste push AUX).
- **Persistance** : `PUT /mount/tuning/cordwrap` push direct AUX.

### 8. Réseau (override host/port app)

- **Geste** : champs texte host + port. Bouton "Tester" qui fait un `GET /state` sur la nouvelle adresse, valide si succès. Bouton "Enregistrer".
- **Persistance** : côté app via `shared_preferences` (clé `astro.host`, `astro.port`). Le `PiHost` v0.1 lit déjà `--dart-define` ; on ajoute la lecture `shared_preferences` qui prend précédence.
- **Pas d'API backend** (rien à persister côté Pi).

### 9. À propos

- **Geste** : aucun, lecture live.
- **Affichage** : versions backend / app / firmware monture, IP courante, SSID, uptime, mDNS hostname.
- Pas de bouton restart (hors scope).

## Modèle d'état (rappel)

**Bus système v0.2 = identique à v0.1** : 5 subsystems (mount, gps, tracking, network, system), aucun ajout. Les capteurs et les calibrations ne sont **pas** sur le bus.

Évolution prévue v0.3 (à anticiper sans implémenter) : ajouter subsystem `alignment ∈ {not_aligned, aligning, aligned}` avec règle d'agrégation `overall = orange` quand `alignment = not_aligned` ET un GoTo est tenté. C'est de la santé contextuelle, pas une lecture live.

## Tests

Couverture cible v0.2 ≈ v0.1 (~50-60 tests Python, ~30-40 tests Dart).

**Backend** :
- Migrations DB : up/down idempotents.
- `calibration_service` : state machine, abort, finalize, error path. Tests `:memory:` SQLite.
- Adapters `lis3mdl`, `adxl345` : fakes I2C qui jouent des séquences pré-enregistrées.
- `nexstar_adapter` AUX additions : fakes série qui répondent aux pass-through bytes.
- Routers : tests REST classiques + SSE (réutilise les helpers v0.1).

**App** :
- Models calibration (parse).
- BLoCs sous-écrans : 1 happy path + 1 abort + 1 erreur par bloc.
- Stream services tilt/compass : 1 happy + 1 reconnect.

## Hors scope explicite

Rappel des items écartés ou déférés :

- Hotspot Pi → backlog.
- `POST /system/restart` → hors scope.
- Sync `S`/`s` (commande HC alignement) → préparé dans `nexstar_adapter` mais consommé en v0.3.
- Catalogue (Messier, planètes, étoiles brillantes) → v0.3.
- Wizard mise en station → v0.3.
- GoTo RA/Dec → v0.3.
- Hub central → v0.3 (pas pertinent en v0.2 vu qu'on a juste Manuel + Setup).
- Subsystem `alignment` sur bus santé → v0.3.
- Custom slew rates, PEC, hibernate → backlog.

## Liens

- Pivot scope : ADR [Setup devient v0.2](../../project/decisions.md)
- Roadmap : [docs/project/roadmap.md](../../project/roadmap.md)
- Référence protocole NexStar : [docs/technical/nexstar-protocol-reference.md](../../technical/nexstar-protocol-reference.md)
- Lib actuelle : [docs/technical/nexstar-capabilities.md](../../technical/nexstar-capabilities.md)
- Modèle d'état : [docs/technical/state-model.md](../../technical/state-model.md)
- API v0.1 : [docs/technical/api.md](../../technical/api.md)
- Hardware : [docs/technical/hardware.md](../../technical/hardware.md)
- Design system : [docs/product/design-system.md](../../product/design-system.md)
- Brainstorm précédent (v0.2 originale = wizard) : Session 11 du journal, conservée pour reprise v0.3.
