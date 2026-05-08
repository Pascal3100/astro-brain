# Archive — Préparation v0.2 Setup (avril–mai 2026)

Sessions 11 à 14. Période couverte : du démarrage du brainstorm v0.2 (2026-04-25) au scaffold de la page Setup avec la carte #8 Réseau livrée (2026-05-03). Quatre sessions qui posent les fondations de la Macro 2 Setup : décisions UX transverses (hub central, AppBar partagée, catalogue backend), réorganisation roadmap (Setup devient v0.2 / mise en station glisse en v0.3), nouvelle arborescence de docs en 3 vues, recherche exhaustive du protocole NexStar (qui débloquera la décision INDI prise en Session 16), assainissement du repo, et premier scaffold Flutter v0.2.

## 2026-04-25 - Session 11 : brainstorm v0.2 démarré, décisions UX prises

> Note : ces décisions ont été prises pour un scope « v0.2 = mise en station + GoTo ». Elles restent **pertinentes** mais pour **v0.3** désormais (cf. Session 12 — Setup devient v0.2).

Ouverture du chantier v0.2 (mise en station 3 étoiles + GoTo, à l'époque). Brainstorm conduit avec la skill `superpowers:brainstorming` + visual companion (mockups dans `.superpowers/brainstorm/65426-1777150786/content/`). Session interrompue avant l'écriture de la spec.

**Décisions arbitrées** (pour v0.3 désormais) :

- **Scope** = alignement 3 étoiles + catalogue minimal (backend canonical : Messier + planètes + ~50-100 étoiles brillantes) + primitive `GoTo RA/Dec`. Catalogue riche (NGC, IC, filtrage tube) reste en v0.4.
- **Repère initial** = capteurs-assistée hybride : compass LIS3MDL + ADXL345 tube lus pour figer le repère initial (tube placé grossièrement horizontal + nord par le user), avec fallback "alignement manuel" si capteurs aberrants.
- **Sélection des étoiles d'alignement** = hybride auto + override : l'app propose une étoile par défaut (logique de visibilité + triangulation), bouton `CHANGER` ouvre une bottom sheet avec la liste filtrée. Étoile 2 ≥ 60° d'arc de la 1ʳᵉ. Étoile 3 idem.
- **Mécanique d'alignement** = `nexstarpy.sync_radec(ra, dec)` après chaque étoile (la monture gère le modèle d'alignement interne). Fallback Pi-side (matrice de rotation + SVD) si pas exposé.
- **Pas de persistance d'alignement entre sessions Pi** : à chaque démarrage backend, on repart de `not_aligned` (le trépied a pu être déplacé).
- **Validation auto via résiduel du fit** : Wahba's problem, SVD/quaternions. Erreur résiduelle max < ~1° → `aligned`. Sinon → restart wizard.
- **GoTo de test post-validation** = bouton optionnel temporaire de dev, à retirer une fois la feature stable.
- **Subsystem `tilt` first-class** dans le modèle d'état système. États `unknown` / `level` / `off_level` / `error`. Détails `{pitch_deg, roll_deg, magnitude_deg}`. Throttle SSE 5 Hz pendant le wizard, 1 Hz autrement.
- **Calibration du compass LIS3MDL** = page dédiée hors wizard. Maintenant absorbée dans **Setup v0.2**.

**Wizard à 6 étapes** (linéaire, sans skip — pour v0.3) :
1. Niveau trépied — bulle virtuelle XY (ADXL345 monture 0x1D), tolérance < 0.5°
2. Calibration départ — tube horizontal + nord, vérif cap ±15°/alt ±5°/cohérence GPS-compass, fallback alignement manuel
3. Étoile 1 — auto-suggestion + override, slew auto, recalage D-Pad rate par défaut 2, `CENTRÉ ✓` → `sync_radec`
4. Étoile 2 — idem, suggérée éloignée ≥ 60°
5. Étoile 3 — idem
6. Validation auto — verdict du résiduel, GoTo de test (dev), TERMINER → `alignment = aligned`

**Mockups produits** : `wizard-overview.html`, `step-niveau.html`, `step-calibration.html`, `step-etoile.html`, `step-validation-v2.html`.

**Décisions UX transverses prises pendant cette session** (toujours valides, applicables dès v0.2) :
- Hub central entre Splash et features (cf. ADR + Session 12).
- AppBar partagée sur tous les écrans (cf. ADR).
- Catalogue côté backend (cf. ADR). Décalé en v0.3 avec le wizard.
- Sur le scope Setup (post-Session-12), le wizard ne passe pas en v0.2 — seules les calibrations capteurs + courses + backlash + network y passent.

## 2026-04-29 - Session 12 : réorganisation roadmap + arborescence docs

Deux pivots majeurs pris pendant la session de brainstorm v0.2 :

**1. Setup devient v0.2** (avant la mise en station)

En détaillant les prérequis du wizard 3 étoiles, constat : impossible d'aligner sérieusement sans compass calibré (LIS3MDL soft-iron offsets), ADXL345 calibrés (zéro ALT, mise à niveau), courses ALT/AZ définies (anti-collision), backlash compensé (tracking + GoTo précis). La page Setup absorbe tout ça plus le network/IP config et l'écran "à propos". Mise en station + GoTo + catalogue minimal passent en **v0.3**. Décalage propagé sur toute la roadmap (cf. `docs/project/roadmap.md` + ADR 2026-04-30 dans `docs/project/decisions.md`).

**2. Nouvelle arborescence de docs en 3 vues**

Inspiration projet réacteur : un seul long doc est dur à maintenir et oblige à charger trop de contexte. On passe à un index global `docs/INDEX.md` qui référence 3 vues :

- `docs/technical/` — archi, hardware, state model, API, deployment
- `docs/project/` — roadmap, decisions (ADRs), journal, backlog
- `docs/product/` — design system, features (1 fiche par feature livrée)

Chaque vue a un `README.md` index. Les docs sont **courts et ciblés** (1 sujet = 1 fichier). La navigation se fait par liens — l'arbre fait office de parcours pour l'agent et pour l'humain. Les chemins et règles de tenue sont reflétés dans `CLAUDE.md`.

**3. Plafond journal = 5-6 sessions max**

Au-delà, on archive par milestone dans `journal/archive/`. Sessions 6, 6-suite, 7 archivées dans `journal/archive/2026-04-backend-v0.1.md` (couvre désormais Sessions 1-7). Le journal courant garde Sessions 8, 9, 10, 11 + cette Session 12.

**Migrations effectuées** :
- Création arborescence : `INDEX.md`, `technical/{README, architecture, hardware, state-model, api, deployment}.md`, `project/{README, roadmap, decisions, backlog}.md` + journal déplacé, `product/{README, design-system, features/manual-control}.md`.
- `git mv` : `docs/backlog.md` → `docs/project/backlog.md`, `docs/journal.md` → `docs/project/journal.md`, `docs/journal/` → `docs/project/journal/`.
- `git rm` : `docs/architecture_hardware.txt`, `docs/hardware_wiring.md` (contenu migré dans `docs/technical/hardware.md`).
- ADRs documentées : pas d'Arduino, REST+SSE pas WebSocket, capteurs en GPIO, ADXL345 vs IMU, Flutter natif vs PWA, BLoC, catalogue backend, hub central, AppBar partagée, Setup→v0.2, doc tree.

**Décisions UX consignées** (à appliquer au scope Setup et au-delà) :
- **Hub central** entre Splash et features (à partir de v0.3 quand il y aura plusieurs features). N'affiche que les entrées actives. Tuiles 2 colonnes (mockup `hub-design.html` G).
- **AppBar partagée** sur tous les écrans : pastille `overall` + tap → Status, toggle thème jour/nuit, bouton reconnect conditionnel offline.
- **Catalogue backend canonical** (skyfield/astropy côté Pi) — l'app est cliente. Inconvénient night planner offline traité plus tard via pattern snapshot/cache (cf. `docs/project/backlog.md`).

**À faire ensuite** :
- Update `CLAUDE.md` avec la nouvelle roadmap, la référence à `docs/INDEX.md`, les paths déplacés, et la règle plafond journal.
- Reprendre le brainstorm avec scope **Setup = v0.2**. Décisions hub/AppBar/catalogue backend valent toujours mais s'appliquent à v0.3 ; pour Setup on a un seul écran + sous-pages calibration. Penser au critère « v0.2 livrée = monture prête à être alignée proprement ».
- Écrire la spec `docs/superpowers/specs/2026-04-30-astro-brain-v02-setup-design.md` une fois le brainstorm bouclé. Self-review puis writing-plans.
- Toujours en parallèle : passe monture quand connecteurs arrivent (sections 3 et 7 de `INTEGRATION_CHECKLIST.md`) pour fermer la v0.1 backend.

## 2026-05-01 - Session 13 : brainstorm v0.2 bouclé + protocole NexStar exhaustivement documenté + assainissement repo

Session longue qui clôt le brainstorm v0.2 Setup et nettoie le repo après les itérations récentes.

**1. Recherche protocole NexStar — l'inconnue principale levée**

Constat : `nexstarpy 0.1.0` est un wrapper minimaliste qui n'expose ni sync, ni backlash, ni cordwrap, alors que la raquette les gère. Recherche complète menée sur la spec officielle Celestron (PDF v1.2 2006) + AUX Commands 1.0 (Andre Paquette 2003) + libnexstar / nexstar-evo / forums INDI.

Conclusion : **toutes ces capacités sont dans le protocole**. Sync `S`/`s` côté HC (firmware ≥ 4.10), backlash + cordwrap côté AUX (pass-through `0x50` vers les motor controllers `0x10`/`0x11` avec msgIds dédiés). C'est `nexstarpy` qui ne wrappe pas — pas le protocole qui ne supporte pas.

Conséquence archi : v0.2 fait du **mount-side** pour cordwrap et backlash (la monture compense elle-même), pas du Pi-side counter. Pour v0.3 le wizard 3 étoiles peut s'appuyer sur `sync_radec` natif (plus besoin de matrice de rotation Pi-side, fallback uniquement si firmware < 4.10).

Deux nouveaux docs sous `docs/technical/` :
- `nexstar-capabilities.md` — ce que `nexstarpy 0.1.0` wrappe (et ne wrappe pas), avec table de mapping vers le protocole.
- `nexstar-protocol-reference.md` — référence exhaustive HC + AUX, pour servir de source quand on étendra l'adapter.

Décision repoussée au plan v0.2 : fork interne de `nexstarpy` dans `backend/astro_brain/adapters/nexstar/` vs chercher une lib plus aboutie.

**2. Brainstorm v0.2 Setup — spec validée**

9 entrées dans Setup : niveau monture, calibration compass, zéro ALT, courses ALT, backlash ALT, backlash AZ, cordwrap AZ, réseau, à propos. Pivot architectural important après une première proposition over-engineered :

- **3 surfaces séparées** : bus système (santé sparse latch-y, inchangé v0.1), sessions de calibration (REST + SSE temporaires), live sensor streams (SSE dédiés à la demande). Pas de conflation entre les trois.
- **Persistance SQLite** (`aiosqlite`, `/var/lib/astro-brain/state.db` via systemd `StateDirectory`) plutôt que JSON files — typage, migrations, requêtes structurées.
- **Pas de cache mount_tuning** : la lecture AUX backlash/cordwrap est ~50 ms, pas la peine de doubler l'état Pi-side.
- **APIs dans le sens du flux de données** : c'est le Pi qui sample I2C, donc l'app suit la calibration via stream — pas de `POST /sample`.

Spec écrite : `docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md` (commit `5f976a6`).

**Mémoire ajoutée** : `feedback_architecture_sharpness.md` — 5 pièges à éviter (conflation bus/live/config, cache sans cause, sur-promotion de helpers en services, APIs à contre-sens, endpoints dangereux mal regroupés). Indexée dans `MEMORY.md` comme "Archi affûtée".

**3. Assainissement du repo**

Audit complet (Explore agent) après les nombreuses itérations de la session :
- `README.md` réécrit (roadmap périmée pointait encore "Motorized focuser + plate solving" en v0.2 ; lien `docs/journal.md` cassé).
- `backend/deploy/INTEGRATION_CHECKLIST.md` — chemin `docs/hardware_wiring.md` → `docs/technical/hardware.md`.
- `docs/project/backlog.md` — formulation "v0.2 (pré-session mise en station)" alignée sur Setup.
- `MEMORY.md` — 3 chemins relatifs corrigés (journal, hardware, backlog).
- Mémoire `feedback_no_venv.md` supprimée : contredisait le passage à `uv` (qui crée un `.venv`).
- Plans + spec v0.1 archivés dans `docs/superpowers/{plans,specs}/archive/` — la v0.1 est livrée.

Commit `ae2b74f`. Push : 5 commits sur `origin/main` (`d4e93a8..ae2b74f`).

**À faire ensuite** :
- **Chantier lib NexStar avant le plan v0.2** : arbitrer fork `nexstarpy 0.1.0` vs lib plus aboutie, puis brainstorm + spec + plan dédiés. Doit exposer ce dont v0.2 (backlash + cordwrap AUX) et v0.3 (sync_radec, is_aligned, goto_in_progress) auront besoin.
- Une fois la lib prête : `superpowers:writing-plans` sur la spec v0.2 Setup.
- Toujours en parallèle : passe monture quand connecteurs arrivent (sections 3 et 7 de `INTEGRATION_CHECKLIST.md`) pour fermer la v0.1 backend.

## 2026-05-03 - Session 14 : scaffold v0.2 Setup + #8 Réseau

Travail Flutter en parallèle pendant que la stack INDI compile sur le Pi. Branche dédiée `feat/v02-setup-scaffold`. Plan focalisé : [`docs/superpowers/plans/2026-05-03-v02-setup-scaffold-network.md`](../../superpowers/plans/2026-05-03-v02-setup-scaffold-network.md). Backend pas touché.

**Task 1 — PiHost runtime** (commit `dd0e828`)

`PiHost` était un `const` lisant uniquement `--dart-define`. Ajout d'une factory `PiHost.fromPrefs(prefs)` qui charge `astro.host` / `astro.port` depuis `SharedPreferences` (précédence : prefs > define > défaut mDNS `astro-brain.local:8000`). `main.dart` build le `PiHost` avant `runApp` ; `AstroBrainApp` reçoit `host` en paramètre. 3 nouveaux tests. 53 anciens toujours verts.

**Task 2 — AstroAppBar partagée** (commit `e4443c2`)

`StatusBar` remplacée par `AstroAppBar(current: AstroScreen)` en HudPanel. L'enum `AstroScreen` (`home`/`system`/`setup`) contrôle quelle icône est désactivée. La pastille `overall` est non-tappable sur System ; le gear `gearSix` est `onPressed: null` sur Setup. Placeholder `SetupScreen` créé. HomeScreen et SystemScreen migrés ; `onOpenSystem` callback supprimé de `_RootRouter`. 2 nouveaux tests widget. Tests : 56 → 58.

**Tasks 3+4 — SetupCard + SetupScreen 9 cartes** (commits `079bd23` + `6b74591`)

`SetupCard` (HudPanel + InkWell) prend `index/icon/label/sublabel/dotStatus/onTap?`. Quand `onTap == null`, la carte est greyed (`textMuted`). `SetupScreen` = `ListView.separated` de 9 cartes avec helper `_cardForIndex`. En v0.2, seule la carte #8 RÉSEAU a un `onTap` (push `NetworkScreen`) ; les 8 autres sont en placeholder désactivé. Ajout de `OverallStatus.gray` (state app, pas backend) pour rendre les pastilles muted des cartes désactivées ; `GlobalDot` mappe `gray → textMuted`. 2 nouveaux tests (9 cartes + seule #8 cliquable). Bug pré-existant fixé en passant : `GlobalDot._pulse` était en `late final` et déclenchait un assert dispose si l'animation ne tournait jamais → init dans `initState`. Tests : 58 → 60.

**Tasks 5+6 — NetworkBloc + NetworkScreen** (commit `d019bc2`)

Pattern bloc complet : `NetworkState` (Equatable, sentinel `copyWith` pour `testError`), `NetworkEvent` (6 events : Loaded/HostChanged/PortChanged/TestRequested/SaveRequested/ResetRequested), `NetworkBloc` :

- `Loaded` → lit prefs (fallback défauts) et hydrate `savedHost`/`savedPort`
- `Test` → `GET http://<host>:<port>/state` timeout 3 s, met `testStatus ∈ {idle, testing, ok, error}`
- `Save` → écrit prefs, met `savedHost/savedPort` à jour (rend `dirty == false`)
- `Reset` → efface prefs, revient aux défauts mDNS

`NetworkScreen` : 2 TextField (host + port int), pastille statut, 3 boutons. **ENREGISTRER** disabled tant que `!dirty || testStatus != ok`. **RÉINITIALISER** toujours actif. Snackbar "Redémarrer l'app pour appliquer" déclenché via `BlocListener` sur changement de `savedHost`. `RepositoryProvider<SharedPreferences>` ajouté à la racine pour permettre au screen de créer son propre bloc. 4 bloc tests + 1 widget smoke test. Tests : 60 → 65.

**État au 2026-05-03 23h00**

Branche prête, 65/65 tests verts, `flutter analyze` clean. Reste : smoke test visuel sur Android physique (à faire pendant la prochaine session quand le téléphone est branché), puis merge `feat/v02-setup-scaffold` → `main`. La stack INDI continue de compiler sur le Pi en arrière-plan (libindi 2.x source build).
