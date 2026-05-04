# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Version active** : `v0.1 livrée` — parité joystick + tracking avec la raquette Celestron via app Flutter native. Backend **89 tests** verts (64 v0.1 + 25 migration INDI) et app 53 tests. Smoke test téléphone fait sur Moto g54 5G. Validation physique faite sur **GPS + compass I2C + network + system** ; **monture pas encore branchée** (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` à dérouler — dongle CP2102 en attente).

**Stack INDI installée** sur le Pi (Session 15) : `libindi` 2.2.0 + driver `indi_celestron_aux` 1.5 + `indi-gpsd` 0.6, via repo Astroberry Debian Trixie arm64 (`https://astroberry.io/debian/`). Driver fonctionnel en test isolé (`indiserver -v indi_celestron_aux` démarre, port 7624, plugins SVD + Nearest).

**Migration backend INDI atterrie sur main** (Session 16) : `MountIndiAdapter` + `AstroBrainIndiClient` + helpers + `FakeIndiClient` côté backend, `indiserver.service` systemd, script de build local du driver patché, doc bascule architecture/deployment/INTEGRATION_CHECKLIST. `nexstarpy` retiré du `pyproject.toml`. Patch C++ backlash mount-axis prêt côté `/tmp/indi-research/indi-3rdparty/` (commit `538810c`, branche `astro-brain-backlash`).

**Cap suivant** : **smoke test E2E sur le Pi** (Task 14 du plan migration) — bloque sur la livraison du **dongle USB-TTL CP2102 5V**. Dès que le dongle arrive : câblage HC RJ12, `bash deploy/install.sh`, fork upstream du patch backlash + build sur le Pi, `INTEGRATION_CHECKLIST.md` sections 0+3+Backlash+Cordwrap. Une fois la checklist verte, ouverture du chantier v0.2 Setup (`superpowers:writing-plans` sur la spec validée Session 13).

**Spec v0.2 validée** : `docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md` (Session 13). En attente smoke INDI hardware.

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12.

## Session en cours

### Session 16 — migration backend mount nexstarpy → INDI atterrie sur main (2026-05-04)

Suite directe de Session 15 (stack INDI installée sur le Pi). Découverte au tour de projet post-cleanup : la branche locale `feat/mount-indi` contenait déjà 15 commits livrant toute la migration backend, écrits en mode `subagent-driven-development` strict (TDD, fresh implementer + double review par task). Décision : rebase de la branche sur `main` (qui avait avancé avec le scaffold v0.2 Setup + cleanup docs INDI), puis revue complète, plutôt que tout réimplémenter.

**1. Rebase `feat/mount-indi` sur `main`**

15 commits rejoués proprement sur `main`. Conflits docs résolus en faveur du contenu le plus à jour : `architecture.md` garde la vue stack INDI (Astroberry + processus systemd) post-Session 15 + restaure le diagramme ASCII enrichi de la branche ; `journal.md` conserve la section "État du projet" consolidée et déplace le contenu Session 14 d'origine vers cette Session 16. Pas de perte de signal côté backend : tous les commits de code branche conservés tels quels.

**2. Récap des commits backend rejoués sur main**

| # | Commit | Sujet |
|---|---|---|
| 1 | `5786484` | helpers purs `_indi_property_helpers.py` (set_number, set_switch, state) |
| 2 | `0b6e92b` | `FakeIndiClient` mirroring de `PyIndi.BaseClient` |
| 3 | `61377d9` | `MountIndiAdapter` skeleton (`start`/`stop` + device discovery 5 s) |
| 4 | `8b4742c` | slew + stop_slew via `TELESCOPE_MOTION_NS/WE` + `TELESCOPE_SLEW_RATE` |
| 5 | `772c94e` | `set_time` / `set_location` via `TIME_UTC` + `GEOGRAPHIC_COORD` |
| 6 | `9e201a9` | `set_tracking` via `TELESCOPE_TRACK_STATE` |
| 7 | `df6a82c` | cordwrap (enabled + position 4 cardinaux) |
| 8 | `18fd745` | backlash 4 valeurs (degrade gracieusement si property absente) |
| 9 | `9d44732` | `AstroBrainIndiClient(PyIndi.BaseClient)` production subclass |
| 10 | `81967fa` | wire `MountIndiAdapter` dans `app.py`, drop `nexstarpy` + `pyserial` |
| 11 | `3449856` | systemd `indiserver.service` + `Requires=` côté `astro-brain.service` |
| 12 | `9ed68da` | script `build-indi-celestronaux.sh` (build .deb sur Pi + apt-mark hold) |
| 13 | `f40b2f7` | docs : bascule `architecture.md` + `deployment.md` + `INTEGRATION_CHECKLIST.md` |
| fix | `f2cb6c3` | `bus.publish` thread-safe via `loop.call_soon_threadsafe` (fix race PyIndi callback) |

**89/89 tests verts** (64 v0.1 + 25 migration INDI) à chaque étape de la branche, validés à nouveau post-rebase.

Patch C++ du driver dans un repo séparé : `/tmp/indi-research/indi-3rdparty/`, branche `astro-brain-backlash`, commit `538810c`. Expose `MOUNT_AXIS_BACKLASH` (Number RW × 4 : `AZ_POS`/`AZ_NEG`/`ALT_POS`/`ALT_NEG`) via les opcodes AUX `0x10`/`0x11`/`0x40`/`0x41`. Conventions modernes du driver respectées (`INDI::PropertyNumber`, dispatch via `processResponse`). Build .deb deferred au Pi (pas de `libindi-dev` sur workstation).

**3. Final review post-rebase**

`superpowers:code-reviewer` (Sonnet) sur `ae29dca..HEAD` pré-fix : **approuvé avec fixes**, aucun issue critique. 2 items "Important" appliqués immédiatement (commit `93e59bc`) :

- `logger.exception(...)` dans chaque `except` de `MountIndiAdapter` (start/stop/slew/stop_slew/set_time/set_location/set_tracking/cordwrap_set_*/set_backlash). Le smoke test Pi sera diagnosticable via `journalctl` au lieu d'un état `error` opaque.
- `active_slews` deep-copié (`[dict(s) for s in ...]`) avant publish bus, côté `MountIndiAdapter` ET `FakeMount`, pour fermer la possibilité qu'une mutation in-place change silencieusement un `SubsystemState.details` déjà émis.

Items "Minor" (~10) non bloquants laissés en suspens — la plupart sont liés à des comportements à observer pendant le smoke test (driver round-trip `TIME_UTC`, vrais noms d'éléments `CORDWRAP_POS`, ordre de lecture env vars). Détail dans le rapport reviewer (non archivé). 89/89 tests verts post-fix.

**4. Hardware en attente — dongle CP2102 5V**

Smoke test E2E (Task 14 du plan migration) bloque sur la livraison du **dongle USB-TTL CP2102 5V** pour le port HC RJ12. Tant qu'il n'arrive pas, la monture ne peut pas être branchée → pas de validation terrain.

**Reprise quand le dongle arrive** :
1. Câbler selon `docs/technical/hardware.md` section "Monture — USB-série via dongle CP2102" (⚠️ vérif multimètre broche 2 RJ12 : peut exposer +12 V selon HC).
2. Sur le Pi : `git pull && bash backend/deploy/install.sh` (installe `indiserver.service` + relance `astro-brain.service`).
3. Forker `indilib/indi-3rdparty` sur GitHub perso, pousser la branche `astro-brain-backlash` depuis `/tmp/indi-research/indi-3rdparty/`, cloner sur le Pi dans `~/code/indi-3rdparty/`, lancer `~/code/astro-brain/backend/deploy/build-indi-celestronaux.sh`.
4. Dérouler `INTEGRATION_CHECKLIST.md` sections 0 (Stack INDI), 3 (Mount), Backlash, Cordwrap. Noter les `### Findings`.
5. Une fois la checklist verte, ouvrir le chantier v0.2 Setup (`superpowers:writing-plans` sur la spec validée Session 13).

**Risques de déploiement à vérifier sur le Pi** (notés dans le plan, lignes 2549-2554) :
- `pyindi-client` indispo en wheel pip → probablement `apt install python3-indi-client` requis. Si `uv sync --extra hardware` échoue à compiler, fallback : paquet apt + venv `--system-site-packages`.
- `INDI_DEVICE_NAME = "Celestron AUX"` est une supposition. À confirmer via `indi_getprop -h localhost '*.CONNECTION'` une fois `indiserver` lancé. Ajuster la constante si besoin.
- `PORT_TYPE` / baud rate : adapter ne pousse pas `PORT_TYPE` ; s'appuie sur le default. Si la connexion échoue, ajouter `PORT_TYPE=PORT_HC_USB` 9600 dans `MountIndiAdapter.start()` après `_await_device`.

**Items deferred au final review de la branche** (volontairement non corrigés ici, à traiter post-smoke-test) :
- `MountIndiAdapter._serial_device` stocké mais jamais poussé au driver via `DEVICE_PORT`. À traiter selon comportement réel : pousser `DEVICE_PORT` si le default ne tape pas `/dev/ttyUSB0`, ou supprimer le champ mort.
- `_await_device()` polle `getDevice()` sur le thread asyncio (pas dans `to_thread`). Reviewer initial juge low-risk pour un flow one-shot de startup ; à reconsidérer si pause observable au boot.

**5. Méta**

Journal au plafond après cette session (Sessions 9-16 = 8 sessions). Prochaine session : archiver Sessions 9-14 dans `journal/archive/2026-04-mount-indi-migration.md` (milestone : migration mount nexstarpy → INDI), garder Sessions 15-16 + la suivante en tête de file.

### Session 15 — install INDI 2.2.0 + driver Celestron AUX sur le Pi (2026-05-04)

Session ops sur le Pi, dans le prolongement direct de Session 14 (où le build INDI from source tournait en arrière-plan pendant le scaffold Flutter v0.2). Plusieurs détours avant de trouver la voie propre.

**1. Diagnostic du build interrompu**

Le `make` source démarré en Session 14 s'était arrêté à 39 % sans message d'erreur dans le log et sans trace OOM dans `dmesg`. Pi rebooté entre-temps (uptime 4 min). Hypothèse retenue : déconnexion SSH → SIGHUP → make tué. Pas un manque de mémoire — zram ~926 Mi tenait largement.

**2. Détour build (~2 h)**

Première tentative de redémarrage encadré : install `tmux`, ajout swapfile disque 2 Go priorité 10 (en backup du zram prio 100), relance `make -j3` détaché en tmux, surveillance via cron 20 min. Build qui dépasse 41 % avec 143 targets construits, swap qui s'allume à 1.3 Go (l'ajout swap était bien utile pour les `.cpp` lourds malgré l'absence d'OOM précédent). Question légitime de l'utilisateur en cours de route : *"si on ne modifie rien, pourquoi compiler ?"*. Première confusion de ma part : j'ai d'abord regardé le paquet `indi-bin` Debian Trixie (1.9.9, sans driver AUX, donc inadapté au cap projet visé en libindi 2.x). J'ai relancé le build source en pensant que c'était la seule option.

**3. Bascule Astroberry après diagnostic réseau**

Sur retour de l'utilisateur (*"pourquoi accepter de faire des choses qui n'ont pas sens ?"*), réexamen complet :

- **PPA mutlaqja** (`ppa:mutlaqja/ppa`) — recommandée par INDI, mais `ppa.launchpadcontent.net:443` rejette activement les connexions TCP depuis le Pi (refus en 47 ms en IPv4 et IPv6). Pas un timeout, un reset actif. Le reste du net fonctionne (Debian, indilib.org). Inutilisable aujourd'hui.
- **Astroberry "old repo"** (`astroberry.io/repo/`) — mort, 404 sur tous les paths apt.
- **Astroberry "new repo"** (`astroberry.io/debian/`) — **actif**, release Trixie arm64 avec clé GPG 2 260 octets, documenté comme source officielle Pi par `indilib.org/download/raspberry-pi.html`.

Inspection du `Packages.gz` Astroberry Trixie : `libindi1` / `indi-bin` / `libindi-dev` en **2.2.0**, `indi-celestronaux` en **1.5**, plus `indi-gpsd 0.6`, `indi-gpsnmea 0.2`, `indi-rpi-gpio`. Tout ce dont la stack INDI a besoin pour l'archi du projet.

**4. Install effective**

Source `astroberry.sources` (deb822) installée à `/etc/apt/sources.list.d/`, clé GPG dans `/etc/apt/keyrings/astroberry.gpg`. Simulation `apt install -s indi-bin indi-celestronaux libindi-dev indi-gpsd` : 0 conflit, 8 paquets nouveaux (6 Astroberry + 2 deps Debian Trixie : `libxisf0`, `librtlsdr0`). Install vrai en moins de 2 minutes.

Vérifs :
- `which indi_celestron_aux` → `/usr/bin/indi_celestron_aux` (195K, daté 2024-08-26)
- `indiserver -v indi_celestron_aux` démarre, écoute port **7624** + socket `/tmp/indiserver`, snoope GPS Simulator + Dome Simulator, enumère 2 math plugins d'alignement (**SVD + Nearest** — bonus utile pour le wizard 3 étoiles v0.3)
- `pascal3100` ajouté automatiquement au groupe `dialout` (accès `/dev/ttyUSB0` quand connecteurs arrivent)

**5. Cleanup**

`/swapfile` 2 Go retiré (swapoff + rm + sed fstab) → retour à zram seul, état initial. `~/code/indi/` (source + 41 % de cache build, 971 Mi) supprimé. Disque libéré : 7.4 Go → 4.5 Go.

**Conséquence pour le cap migration INDI**

L'ADR `2026-05-01 — Pilotage monture via INDI (drop nexstarpy)` avait déjà tranché : on bascule sur `indi_celestron_aux` + `pyindi-client`. Cette session **concrétise la Task 0** du plan `docs/superpowers/plans/2026-05-01-mount-indi-migration.md` (install Pi de la stack INDI). Capacités vérifiées en sanity check (sync, alignement SVD + Nearest, properties cordwrap, slew rates 8 niveaux) cohérentes avec la couverture documentée dans `docs/technical/indi-reference.md`. Le seul vrai trou identifié reste **backlash mount-axis 4 valeurs** (opcodes `MC_*_BACKLASH` non câblés dans `auxproto.h` du driver), traité côté plan migration via patch upstream.

Reste à faire côté plan migration (cf. `docs/superpowers/plans/2026-05-01-mount-indi-migration.md`) : `MountIndiAdapter`, retrait de `NexStarMountAdapter` + extra hardware `nexstarpy`, unit systemd `indiserver.service`, smoke test connecteurs branchés.

**Refs**
- Repo : `https://astroberry.io/debian/` — clé `/etc/apt/keyrings/astroberry.gpg`, sources `/etc/apt/sources.list.d/astroberry.sources`
- Nouvelle ADR ajoutée : `2026-05-04 — Stack INDI installée via repo Astroberry Debian Trixie arm64` (cf. `docs/project/decisions.md`)

### Session 13 — brainstorm v0.2 bouclé + protocole NexStar exhaustivement documenté + assainissement repo (2026-05-01)

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

### Session 14 — scaffold v0.2 Setup + #8 Réseau (2026-05-03)

Travail Flutter en parallèle pendant que la stack INDI compile sur le Pi. Branche dédiée `feat/v02-setup-scaffold`. Plan focalisé : [`docs/superpowers/plans/2026-05-03-v02-setup-scaffold-network.md`](../superpowers/plans/2026-05-03-v02-setup-scaffold-network.md). Backend pas touché.

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

### Session 12 — réorganisation roadmap + arborescence docs (2026-04-29)

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

### Session 11 — brainstorm v0.2 démarré, décisions UX prises (2026-04-25)

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

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
