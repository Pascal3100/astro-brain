# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Roadmap restructurée 2026-05-05** : abandon du versioning v0.X, passage à un train de macro-étapes (voir [`roadmap.md`](roadmap.md) + ADR du 2026-05-05). Les sessions antérieures continuent de référencer `v0.X` ; correspondance : v0.1 = Macro 0 Socle, v0.2 = Macro 2 Setup, v0.3 = Macro 3 Mise en station, v0.4 = Macro 4 Catalogue, v0.5 = Macro 5 Caméras, v0.6 = Macro 6 Focus + MES, v0.7 = Macro 7 Astrophoto. La migration INDI devient sa propre Macro 1 (technique).

**Macro 0 — Socle ✅** (livré 2026-04-25) : parité joystick + tracking via app Flutter native. Backend **89 tests** verts (64 socle + 25 migration INDI), app 53 tests. Smoke téléphone Moto g54 5G. Validation physique GPS + compass I2C + network + system. **Monture désormais pilotée end-to-end** (pont ESP32, Macro 1 bouclée S37) ; la passe physique mount-branchée de l'`INTEGRATION_CHECKLIST.md` (sections 3 et 7) reste à cocher formellement.

**Macro 1 — Migration INDI ✅** (bouclée 2026-07-05, S37) : `MountAdapter` `nexstarpy` → stack INDI (`indiserver` + `indi_celestron_aux` 1.5 + `pyindi-client`), `nexstarpy` retiré. La liaison Pi↔monture — bloquée ~10 sessions (S26→S33) par le bus AUX single-wire — a été résolue par un **pont ESP32** (WiFi↔TCP 2000) + interface RX LM2902 / TX 74AHCT125 ([ADR 2026-07-05](decisions.md)). Chaîne `app REST → FastAPI → pyindi-client → indiserver → pont ESP32 → bus AUX → moteur` **prouvée end-to-end** (`POST /slew` fait tourner la vraie monture). Détail archivé : [S26→S33](journal/archive/2026-06-bus-aux.md) + [S34→S37](journal/archive/2026-07-macro1-liaison.md). Reconnexion auto + manuelle ajoutées et validées (S38→S39).

**Macro 2 — Setup ✅** (done 2026-07-08) :
- ✅ Carte #8 RÉSEAU livrée (Session 14).
- ✅ Slice INFRA livré (Session 17, 8 commits, +29 tests) — sqlite `state.db` + repos calibration/limits.
- ✅ **Slice A capteurs livré** (Session 18, 2026-05-07) : items #1 niveau monture, #2 compass LIS3MDL, #3 zéro ALT. Fixes review v0.2 (B1, B2, I1-I7, N1-N10) + refactor I8 (`CalibrationBloc` partagé entre les 3 capteurs, -784 LOC). Tests : 178 backend + 115 frontend.
- ✅ **Slice B Courses ALT livré** (Session 19, 2026-05-07) : item #4. Backend `/limits/alt` GET/PUT + écran Flutter capture ALT_min/max via `TiltStreamService`. Tests : 183 backend + 130 frontend.
- ✅ **Slice C About livré** (Session 19, 2026-05-07) : item #9. Backend `GET /about` (versions, IP/SSID, uptime, started_at) + écran Flutter read-only avec bouton RAFRAÎCHIR. Tests : 191 backend + 133 frontend.
- ➡️ **Backlash mount-side déplacé en Macro 5** (Session 41, 2026-07-08) : le driver `indi-celestronaux` v1.5 n'expose pas `MOUNT_AXIS_BACKLASH` → nécessite un fork/patch C++ ; valeur réelle en imaging seulement. Macro 2 déclarée **done** sans lui. Cf. ADR 2026-07-08.
- ➡️ **Retrait des 2× ADXL345 + feature Courses ALT** (Session 42, 2026-07-17) : items niveau monture (#1), zéro ALT (#3) et Courses ALT (#4) ci-dessus **retirés** (capteurs jamais installés physiquement, hors chemin de pointage depuis l'ADR 2026-05-10, garde-fou ALT jamais enforcé). Compass LIS3MDL (#2) conservé, désormais en heading non tilt-compensé. Cf. ADR 2026-07-17.

**Macro 3 — Mise en station + GoTo basique 🚧** :
- ✅ Item #1 Hub central (Session 20).
- 🚧 Item #2 Wizard alignement 3 étoiles : implémentation software complète (backend + Flutter, 22 tasks plan, Session 22). Validation matérielle à faire (liaison monture OK depuis Macro 1 / S37) — **prochain vrai jalon**.
- 🚧 Item #3 GoTo réel + #5 Page Catalogue : software livré (backend + Flutter, 19 tasks plan, Session 24). Validation matérielle (slew réel) à faire (liaison OK depuis S37).
- 🚧 Item #4 Catalogue : tranche A stars (Session 23) + enrichissement visibilité `visible_now` (Session 24). Messier/planètes à suivre.
- 🚧 Aide étoile/constellation (rattachée #2 wizard) : `ConstellationChart` au trait + navigateur par constellation + chaîne de position fix Pi → téléphone → sinon pas de wizard (fallback Paris supprimé) — software livré Session 25.

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12.

## Session en cours

### Session 43 — Oracle tranche 1 : producteur `oracle/` + CI de référence (livré 2026-07-24, journalisé 2026-08-08)

> Entrée **rétroactive** : le chantier a été livré le 2026-07-24 (13 commits, `5c3d6b4`→`827ba1a`) mais jamais journalé sur le moment ; comblé le 2026-08-08 après vérification du CI en prod.

Objectif : poser le **plan de données de référence autonome du Pi** (fil transverse « Oracle / Éphémères », hors train de macros — [ADR 2026-07-24](decisions.md) + [spec](../superpowers/specs/2026-07-24-oracle-ephemeres-design.md)) sur son premier cas utile, les **comètes**. Plan suivi : [`2026-07-24-oracle-producer.md`](../superpowers/plans/2026-07-24-oracle-producer.md), **9 tâches, TDD**.

**Livré — module `oracle/` (producteur, tourne en CI, jamais sur le Pi).** Projet Python indépendant (`uv`, zéro dépendance vers `backend/`/`app/`) : fetch MPC `CometEls.txt` avec **fallback bundlé** (le build ne casse jamais si le fetch échoue) → dédup par ligne entière (pas `groupby.last` qui mélangeait les époques) → **éphémérides skyfield** RA/Dec **apparentes of-date (JNow)** + magnitude prédite sur une **fenêtre glissante 60 j** (kernel `de421.bsp` commité → build offline et déterministe) → `reference.sqlite` (**schéma versionné v1**, `schema.sql` = contrat) → `manifest.json` (`sha256`, `sqlite_url`, fenêtre). Entrée CLI `python -m oracle`. **13 tests verts** (`uv run pytest tests/` — pas de `testpaths`, passer `tests/` explicitement).

**Livré — CI `.github/workflows/oracle.yml`.** Cron hebdo (lundi 04:17 UTC) + push `main` sur `oracle/**` + `workflow_dispatch` ; publie une **release rolling `almanac-latest`** (assets `reference.sqlite` + `manifest.json`). Branch filter : seul `main` publie.

**Vérifié en prod (2026-08-08, lecture seule).** 3 runs `oracle-reference` **tous verts** ; release `almanac-latest` bien publiée par `github-actions[bot]`, les 2 assets présents. Le **cron hebdo tourne réellement** : manifest publié le plus récent `generated_at 2026-08-03T07:50Z` (postérieur aux commits du 24 → run cron), `schema_version 1`, fenêtre `2026-08-03`→`2026-10-01` (60 j), `sha256` renseigné. **Contrat consommateur opérationnel.**

**Reste (hors cette tranche producteur) :** les **consommateurs** — app Flutter + Pi (cache local `reference.sqlite`, interrogation hors-ligne, notifs locales) — et les tranches suivantes (événements calculés, appulses). Le discriminant oculaire/photo est couplé Setup tube (Macro 4) / caméras (Macro 5), hooks laissés. Roadmap : ligne « Oracle / Éphémères » marquée « tranche 1 producteur livrée ».

### Session 42 — Retrait ADXL345 + Courses ALT (2026-07-17)

**Décision** : retirer les 2× ADXL345 (`0x53` tube, `0x1D` monture) et la feature Courses ALT — code, endpoints, écrans Flutter, câblage, docs. Garder le compass LIS3MDL (`0x1E`) et le GPS. Cf. **ADR 2026-07-17** dans [`decisions.md`](decisions.md) (supersède l'ADR 2026-04-24).

**Contexte de la décision** : l'installation physique du tube sur la monture n'a jamais été faite. La faire maintenant imposerait de concevoir/imprimer 2 boîtiers 3D pour des capteurs dont la valeur s'est effritée : le modèle SVD/sync natif (ADR 2026-05-10) a mis les ADXL hors du chemin de pointage depuis mai, et un audit de code mené pendant ce retrait a confirmé que la feature Courses ALT n'a **jamais gardé** un slew réel (aucun code de commande n'était conditionné par une lecture tilt) — retrait doc-only sur ce point, pas une régression de sécurité active.

**Périmètre** : backend (services + routes + adapters ADXL), app Flutter (écrans calibration ADXL ×2, courses ALT, bulle virtuelle), schémas de câblage (Task 6, hors scope de cette session docs), et cette passe de documentation (ADR, hardware, roadmap, backlog, CLAUDE.md, README, api/state-model/architecture).

**Conséquence principale** : le compass LIS3MDL passe en heading **non tilt-compensé** (plus d'ADXL co-localisé pour fusionner l'inclinaison) ; la mise à niveau redevient **bulle physique** trépied ; l'anti-collision ALT est repoussée en **Macro 3** via la position monture rapportée par le driver.

**Backlog** : 5 pistes prospectives capturées dans [`backlog.md`](backlog.md#reprise--résilience--aide-au-pré-pointage-post-retrait-adxl-macro-3) (résilience reboot Pi en priorité, home/parking + seed-sync, set-zéro ALT à la bulle, compass déporté + déclinaison, coupure totale non gérée).

### Session 41 — Macro 2 refermée : backlash mount-side différé en Macro 5 (2026-07-08)

Objectif : finaliser Macro 2 Setup (dernier item = backlash mount-side ALT/AZ, historiquement bloqué liaison, débloqué depuis S37). **Inventaire d'abord** (agent Explore) puis **vérification du seul fait qui décide du scope**.

**Le driver ne gère pas le backlash d'axe — vérifié, pas supposé.** Inventaire : l'adapter backend `get_backlash`/`set_backlash` (vecteur `MOUNT_AXIS_BACKLASH`, éléments `ALT_POS/ALT_NEG/AZ_POS/AZ_NEG`, validation 0–99) + fake + **5 tests** sont déjà écrits ; manquent la route REST, la persistance, et tout le Flutter (cartes Setup 5/6 = placeholders inertes). Mais `set_backlash` lève volontairement `RuntimeError` tant que le driver n'advertise pas la propriété. Vérif sur le Pi (read-only) : `indi-celestronaux 1.5` / `indi-bin 2.2.0`, `strings` du binaire → **seulement `FocuserInterface::SetFocuserBacklash`** (focuser), **aucun `MOUNT_AXIS_BACKLASH` ni `MC_*_BACKLASH` d'axe**. ⇒ le backlash mount-side **n'existe pas dans le driver stock** ; l'exposer exige un **fork + patch C++** (~70 lignes) puis build sur le Pi.

**Décision (arbitrée avec l'utilisateur) : différer proprement, pas patcher maintenant.** Le backlash ne paie qu'en imaging/guidage (Macro 5+) ; pour manuel + 3 étoiles + GoTo basique il est inutile (roadmap le classait déjà 🌫 différable). Le vrai coût est du C++ driver (famille « stack INDI »), pas du chantier Setup. ⇒ **backlash mount-side sorti du train Macro 2, rattaché à Macro 5** ; **Macro 2 déclarée done** sur son critère (calibrations niveau/compass/zéro-ALT + courses ALT + réseau + à-propos, tous accessibles depuis l'app et persistés). **Aucun code jeté** : l'adapter + les 5 tests restent en l'état, prêts pour le jour où le driver sera patché.

**Livré cette session (0 C++, doc + UI) :** cartes Setup 5/6 marquées « Reporté — Macro 5 » (`_placeholder` rendu paramétrable, cordwrap #7 inchangé) — `flutter analyze` clean ; **ADR 2026-07-08** (backlash différé, driver v1.5 vérifié) ; roadmap (Macro 2 ✅ done, item déplacé en Macro 5 avec prérequis fork driver, renvoi depuis Macro 1) ; ce journal.

**🔜 Reprise :** le prochain vrai jalon est la **validation matérielle du wizard 3 étoiles / GoTo** (ferme Macro 3 + débloque le vrai test tracking, cf. S40).

### Session 40 — App release muette : cause racine = permission INTERNET manquante (2026-07-08)

Reprise sur « l'app reste bloquée au premier écran (splash) et le RETRY n'arrive pas à reconnecter ». Skill `systematic-debugging`, validation directe sur le Moto g54 (`adb`, captures d'écran).

**Fausse piste écartée d'abord.** Le splash affichait « ASTRO-BRAIN NOT REACHABLE ». Hypothèse initiale (prefs effacées → hôte retombé sur `astro-brain.local` que le mDNS Android ne résout pas) : **réfutée par preuve** — le téléphone joignait le backend (`nc 192.168.1.36:8000` exit 0, ping 0% perte), et **même en saisissant l'IP directe dans Setup → Réseau, le TESTER échouait** avec la même erreur.

**Cause racine (message d'erreur complet via `uiautomator dump`).** `SocketException: Connection failed (OS Error: Operation not permitted, errno = 1)` = **EPERM** — l'OS refuse la socket à l'app, pas un problème réseau. Vérif des manifests : `debug/` et `profile/AndroidManifest.xml` déclarent `INTERNET`, **`main/AndroidManifest.xml` ne l'a pas**. Flutter n'injecte INTERNET **que** dans debug/profile → l'APK **release** n'a aucun accès réseau. Masqué jusqu'ici car tous les smoke tests étaient en debug/profile ; **S39 = premier build `--release`** → bug révélé. Voir [[project_flutter_release_internet]].

**Fix.** Ajout de `<uses-permission android:name="android.permission.INTERNET"/>` dans `main/AndroidManifest.xml`. Rebuild `--release` + réinstall → **app connectée end-to-end** : pastille rouge INACTIF (offline) → **orange ALERTE** (= `overall` réel du backend, orange à cause du GPS `no_fix`), bannière GPS backend affichée. L'hôte est resté `astro-brain.local` (prefs re-effacées par `flutter install`) et la connexion marche quand même → une fois INTERNET présent, Dart résout le mDNS sur ce téléphone (la note S39 « pointer sur l'IP » n'était donc pas la cause).

**Points annexes relevés :** (1) `flutter install` désinstalle toujours avant d'installer → efface les `SharedPreferences` (c'est ce qui « perdait » l'IP) — **laissé tel quel** (comportement outil).

**Deux bugs annexes corrigés (TDD, même session).** (2) **Affichage splash en échec** : `_stepStatus` rendait les 3 étapes cochées vertes ✓ en phase `failure` (car `failure` = dernier index de l'enum > toutes). Ajout de `SplashState.failedPhase` (phase où l'échec s'est produit, posée dans le `catch` du cubit) ; logique extraite en fonction pure testable `stepStatusFor` : étapes avant l'échec = faites, celle en échec = erreur (✗ rouge), suivantes = en attente. Vérifié on-device (WiFi coupé) : CONTACTING ✗ rouge, les 2 autres en attente. (3) **Récupération d'hôte depuis l'écran d'échec** : bouton **CONFIGURER LE RÉSEAU** ajouté sous RETRY/CONTINUE OFFLINE → pousse directement `NetworkScreen` (plus besoin du détour CONTINUE OFFLINE → Setup → Réseau). Navigation vérifiée on-device. Modèle « redémarrer pour appliquer » de l'écran Réseau inchangé. **+8 tests splash (237 au total), analyze clean.**

**Validation matérielle (app communicante).** **Mode manuel D-Pad → vraie monture : confirmé par l'utilisateur.** Puis vérification du **tracking** : le chemin de commande est **vert** (`POST /tracking {true}` → `{"ok":true}`, SSE `tracking:sidereal`, INDI `TELESCOPE_TRACK_STATE.TRACK_ON=On`, et OFF au disable). En revanche **aucun mouvement moteur** sur 60 s de tracking ON (encodeur `HORIZONTAL_COORD` AZ/ALT identique au 17ᵉ chiffre). Contrôle : un slew manuel az+ 3 s @8x fait bien bouger l'encodeur (359,54°→3,59°) → **le readback est live**, donc la monture ne suit réellement pas. **Ce n'est pas un bug** : la monture n'est pas alignée, elle se croit à DEC ≈ 84° (6° du pôle) et ALT ≈ −5° (sous l'horizon) → le driver alt-az calcule un taux sidéral ≈ 0. Confirmé conceptuellement : sur une monture **alt-az**, pas d'alignement = pas de suivi utile (le driver n'oppose pas de garde logicielle, mais la géométrie donne un taux nul). Le vrai test du tracking (étoile centrée plusieurs minutes) appartient donc à l'étape alignement-sur-matériel. Un « test rapide » possible (sync jetable vers une cible hors-pôle au-dessus de l'horizon → dérive ~0,25°/min) gardé sous le coude comme outil de debug si le test de nuit échoue. Monture laissée tracking OFF.

**🔜 Reprise :** valider le **wizard 3 étoiles / GoTo** contre le matériel (débloque le vrai test tracking) + rouvrir Macro 2 (backlash mount-side).

### Session 39 — Déploiement S38 + validation matérielle (auto-connexion boot, reconnexion manuelle) (2026-07-07)

Reprise du handoff S38 (« déployer + valider à froid »). Skills `systematic-debugging` (bug on-device) + `test-driven-development`. Édition + tests workstation, exécution/validation sur le Pi (IP directe `192.168.1.36`, alias `astro-brain` en route morte comme noté S33).

**Déploiement backend (S38 = 2 commits) → 3ᵉ bug on-device démasqué immédiatement.** `git pull` (`99eea16`→`4092b14`) + restart service → au boot, `mount:error`, `CONNECT=Off`. Logs : `_ensure_connected()` (Fix A) lève `KeyError: 'CONNECT'` sur `find_widget(conn, "CONNECT")`. **Diagnostic sans devinette (introspection live pyindi sur le Pi)** : après `connectServer`, l'arbre de propriétés arrive **en streaming** — `getDevice` rend d'abord un **device placeholder** (nom `""`, vecteur `CONNECTION` à **16 widgets sans nom**, t≈20 ms), puis le device complet (`CONNECT`/`DISCONNECT`, t≈120 ms). `_ensure_connected` lisait `CONNECT` à t≈0 → crash → `start()` échoue → **jamais auto-connecté** (et le superviseur ne réessaie que sur `disconnected`, pas `error`). **Même famille que le device périmé S37.**

**Fix (TDD).** `_await_connection_switch()` : poll (re-fetch device à chaque tour, jamais caché) jusqu'à ce que le widget `CONNECT` existe, borné `CONNECT_CONFIRM_TIMEOUT_S` ; tolérance fake préservée (`getSwitch` None au 1er tour = pas de `CONNECTION` → skip). Test RED reproduisant placeholder→complet (KeyError identique à l'on-device) → GREEN. **354 tests backend, ruff clean.** Commit `b816151`, déployé.

**Validations matérielles (le cœur du handoff).**
- **Fix A (auto-connexion boot) ✅** : après restart, **sans aucune action manuelle**, `indi_getprop CONNECT=On` + `curl /state` → `mount:ready`. Le point qui bloquait tout depuis S38 (connexion montée à la main) est fermé.
- **Hypothèses pyindi du superviseur — confirmées on-device** : `isServerConnected()` existe et bascule True/False ; re-`connectServer()` sur la **même instance** après un drop renvoie True et reconnecte → la branche socket de `reconnect()` est valide sur le vrai binding.
- **Fix C (reconnexion manuelle) ✅** : `indi_setprop DISCONNECT=On` (le `CONNECT=Off` seul est ignoré — switch 1-of-many) → `CONNECT=Off`, puis `POST /mount/reconnect` → `{"ok":true}`, après ~5 s `CONNECT=On` + `ready`. C'est exactement le job du bouton RECONNECTER (même primitive `reconnect()`→`_ensure_connected`→`_await_connection_switch`).
- **Fix C (superviseur auto)** : **non isolable proprement on-device** — l'unit systemd a `Requires=indiserver.service` + `After=`, donc `systemctl restart indiserver` **propage un restart à astro-brain** (PID observé 1798→1977, `NRestarts=0`) → c'est Fix A qui re-connecte, pas le superviseur. Bilan : la **mort d'indiserver est couverte par systemd+Fix A** ; le superviseur couvre les **blips de socket transitoires** (indiserver vivant) — logique unit-testée (`test_mount_connection_supervisor.py`) + primitives pyindi confirmées ci-dessus.
- **Observabilité corrigée** : le backend tourne au niveau racine **WARNING** en prod (vérifié) → les logs `INFO` du superviseur (« reconnect attempt N » / « reconnected ») étaient **invisibles**. Remontés en `warning` (perte + récup du lien = événements ops notables ; le back-off borne le spam). Commit `fa42e52`, déployé (`fa42e52` sur le Pi, boot auto-connect re-vérifié vert).

**App.** `flutter analyze` clean → `flutter build apk --release` (54,7 Mo ; 1 OOM Gradle transitoire, OK au 2ᵉ essai) → `flutter install --release` sur le Moto g54 (ZY22K7BHL4, ancienne version désinstallée) → app lancée. Livre le code S38 (rate clampé 1..8, `MountStatusBanner`, bouton RECONNECTER).

**⚠️ Reste à valider par l'utilisateur (visuel, monture sous tension) :** (1) **D-Pad** de l'app → doit bouger la vraie monture (backend prêt : `CONNECT=On`, `mount:ready` ; app pointée sur `192.168.1.36` via Setup → Réseau — Android ne résout pas `.local`) ; (2) bouton **RECONNECTER** de la bannière quand la monture est coupée. Note : une observation live de l'encodeur AZ (10 s) est restée figée à `360` (position défaut) — soit pas de tap, soit **monture non alimentée** pendant le test (l'ESP32 `.200` répondait, handshake OK, mais moteurs muets → pas de lecture d'encodeur).

**🔜 Reprise :** une fois le D-Pad confirmé visuellement, rouvrir **Macro 2** (backlash mount-side, débloqué) + valider **wizard 3 étoiles / GoTo** contre le matériel (même path adapter, corrigé).

### Session 38 — Mode manuel app→monture : cause racine = driver non reconnecté + fix auto-connexion (2026-07-06)

Reprise après « le mode manuel de l'app ne marche pas » (contredit S37). Skill `systematic-debugging`. Le end-to-end validé en S37 était un **curl direct** au backend ; le chemin **app→backend n'avait jamais été testé**.

**Cause racine (confirmée live, lecture seule).** Symptôme : D-Pad actif, `POST /slew` → 200, **aucune erreur, aucun mouvement, à tous les rates**. Diag Pi : `Celestron AUX.CONNECTION.CONNECT=**Off**` + `No TELESCOPE_SLEW_RATE` → **le driver INDI n'était plus connecté à la monture**. En S37 la connexion avait été montée **à la main** (`indi_setprop …CONNECT=On`) et rien ne la rétablit → au retour elle est `Off`. `indiserver` **annonce** le device même déconnecté (`_await_device` passe), mais aucune propriété monture n'existe → `slew()` lève, publie `mount:error` via SSE… mais renvoie quand même **200** → app muette. Confirmé en reconnectant à la main : `CONNECT=On` → `TELESCOPE_SLEW_RATE` 1x→8x réapparaît, D-Pad **bouge la monture** (validation utilisateur).

**Fix A — auto-connexion backend (TDD).** `MountIndiAdapter.start()` appelle désormais `_ensure_connected()` : pousse `CONNECTION.CONNECT=On` et attend la confirmation (`CONNECT_CONFIRM_TIMEOUT_S=8s`) avant de publier `ready`. Tolérant au driver sans `CONNECTION` (fakes) : warn + continue. Test RED→GREEN + ajustement d'un test slew (drop du push CONNECTION). **345 tests backend, lint OK.** Effet de bord assumé : monture éteinte au boot → `start()` échoue proprement → `mount:error` (désormais **visible**, cf. B2) au lieu d'un faux `ready` silencieux ; pas de reconnect auto (⇒ étape suivante).

**Fix B — bugs app qui masquaient l'échec.** (B1) rate clampé **1..8** (`ManualBloc`) + `RateControl(max: 8)` — le `9x` n'existe pas côté INDI et cassait tout slew à 9. (B2) nouveau `MountStatusBanner` sur l'écran manuel → affiche `Erreur monture` / `Monture déconnectée` + message SSE quand la monture n'est pas pilotable (fini l'échec invisible). **229 tests Flutter, analyze clean.**

**Commit `3ac2ebe`** (Fix A + B, 345 backend / 229 Flutter). Puis, à froid, conception de la **reconnexion INDI** (analyse de l'existant avant code).

**Fix C — reconnexion `indiserver` (auto + manuel, une seule primitive).** Constat existant : `AstroBrainIndiClient.serverDisconnected` **détectait** déjà la chute mais publiait `error` + « redémarrez le service », sans toucher `adapter._connected` ni reconnecter ; le pattern de tâche de fond abonnée au bus existait (`Orchestrator`, `AlignmentInvalidator`). Conception retenue (couches : le retry app↔Pi ne couvre pas le lien Pi↔monture — cas monture éteinte au boot = app OK) :
- **Sémantique** : `serverDisconnected` routé via l'adaptateur (hook `on_disconnect`) → `_connected=False` + publie **`disconnected`** (pas `error`) ; `error` réservé aux échecs de commande récupérables. Distinction nette lien-perdu vs commande-ratée, cohérente avec `AlignmentInvalidator`.
- **Primitive** `MountIndiAdapter.reconnect()` (Lock-guardée) : re-`connectServer` si socket tombé (`isServerConnected()`), `_await_device`, `_ensure_connected` ; publie `connecting→ready`, ou `disconnected` en échec (pour laisser le superviseur réessayer). `request_reconnect()` = fire-and-forget non bloquant.
- **Superviseur** `MountConnectionSupervisor` (même moule que l'Orchestrator) : sur `disconnected`, réessaie `reconnect()` en **back-off** `[1,2,5,10,30]s` jusqu'à `ready` ; ignore `error`. Lancé en tâche de fond du lifespan (annulé avant `mount.stop()`).
- **Manuel = nudge** : `POST /mount/reconnect` (non bloquant) + bouton **RECONNECTER** sur la bannière B2 → `ManualReconnectPressed`. Récup auto (app fermée ou non) **+** bouton pour forcer.
- **Défense en profondeur** : borne API `SlewRequest.rate` resserrée `le=9 → le=8` (le `9x` n'existe pas). Commit `ad9d17f`. **353 backend + 231 Flutter verts** (fichiers touchés lint/analyze-clean ; 28 erreurs ruff préexistantes hors-scope laissées telles quelles).
- ⚠️ **Piège de test Flutter rencontré** : un test widget tapait le bouton RECONNECTER câblé à un **vrai `ManualBloc`** (handler async + `bloc.close()`) → **hang de 10 min** (timeout par défaut) qui bloquait toute la suite. Fix : `MockBloc<ManualEvent, ManualState>` + `verify(add(...))` (le chemin api est couvert par le test bloc). Voir [[flutter-widget-test-mockbloc]].

**⚠️ État de fin de session : tout est commité + poussé sur `main` (`3ac2ebe` puis `ad9d17f`), mais RIEN n'est déployé ni validé sur le matériel.** La monture ne marche « maintenant » que parce que la connexion a été montée **à la main** en début de session (`indi_setprop …CONNECT=On`) — au prochain power-cycle elle retombera tant que le nouveau backend n'est pas déployé.

**🔜 Reprise demain (ordonnée) :**
1. **Déployer** : sur le Pi `cd ~/code/astro-brain && git pull && systemctl restart astro-brain.service`.
2. **Confirmer 2 hypothèses pyindi on-device** (non testables workstation) : `client.isServerConnected()` existe **et** re-`connectServer()` marche sur la même instance après un drop. Si faux, adapter `reconnect()`.
3. **Valider A (auto-connexion boot)** : après restart, sans action manuelle, `indi_getprop "Celestron AUX.CONNECTION.CONNECT"` = `On` + `curl /state` → `mount:ready`.
4. **Valider C (auto-retry)** : `indi_setprop "Celestron AUX.CONNECTION.CONNECT=Off"` (ou couper l'ESP32) → vérifier dans `journalctl -u astro-brain` les logs « mount supervisor: reconnect attempt N » + retour `ready` seul.
5. **Valider C (manuel)** : `curl -XPOST …/mount/reconnect` → `ready`.
6. **Côté app** : re-tester le **D-Pad** (doit bouger la monture) + le bouton **RECONNECTER** de la bannière quand la monture est coupée.
7. Puis rouvrir **Macro 2** (backlash mount-side, débloqué) + valider **wizard 3 étoiles / GoTo** contre le matériel (même path adapter, corrigé).

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
- [`2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) — Sessions 11→14 : préparation v0.2 Setup — brainstorm v0.2, réorganisation roadmap + arborescence docs en 3 vues, recherche exhaustive du protocole NexStar + assainissement repo, scaffold Flutter + carte #8 Réseau livrée.
- [`2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) — Sessions 15→16 : install stack INDI 2.2.0 + driver Celestron AUX sur le Pi (Astroberry Trixie arm64), rebase + merge backend `MountIndiAdapter` + `pyindi-client` sur main (89 tests verts, `nexstarpy` retiré). Smoke test E2E reste bloqué par dongle CP2102.
- [`2026-05-macro2-setup.md`](journal/archive/2026-05-macro2-setup.md) — Sessions 17→19 : Macro 2 Setup Slices INFRA (sqlite `state.db` + repos calibration/limits, 8 tasks INFRA), A capteurs (ADXL345 ×2 + LIS3MDL, refactor `CalibrationBloc` partagé -784 LOC), B (courses ALT) + C (À propos). Items #1 #2 #3 #4 #8 #9 livrés ; Slice D backlash/cordwrap reste bloqué dongle CP2102.
- [`2026-05-macro3-software.md`](journal/archive/2026-05-macro3-software.md) — Sessions 20→25 : Macro 3 tranche logicielle — Hub central (#1), wizard alignement 3 étoiles (#2, modèle natif Celestron via `sync_radec`), GoTo réel + page Catalogue (#3/#5), catalogue backend stars IAU CSN (#4 tranche A), aide étoile/constellation + chaîne de position fix Pi→téléphone. Validation matérielle de tout reportée derrière la liaison monture (Macro 1, fil S26+).
- [`2026-06-bus-aux.md`](journal/archive/2026-06-bus-aux.md) — Sessions 26→33 : fil matériel liaison monture (Macro 1), bring-up — identification du bus AUX NexStar SLT, diagnostic single-wire (diode 1N4007 → 0,97 V, puis 2× BC547 → 0,05 V), **cause racine ÉLECTRIQUE prouvée** (tap pas haute-Z déforme la ligne, diodes de clamp GPIO 3,3 V vs bus 4,4 V), **pivot ESP32** (jalons A+B verts, la monture bouge via le pont TCP), étage RX HEF4093BP prouvé de bout en bout (S31-S32) + perturbation du bus résolue (Rpu retiré), RX comparateur LM2902 prouvée + TX round-trip tranché → 74HC125 (S33).
- [`2026-07-macro1-liaison.md`](journal/archive/2026-07-macro1-liaison.md) — Sessions 34→37 : fil liaison monture (Macro 1), 2ᵉ moitié — refonte des schémas de câblage HTML + pivot TX 74AHCT125 acté en doc (S34), **hardware AUX validé, le moteur répond** (round-trip TX via 74AHCT125/LM2902, S35), turnaround TX→RX résolu (round-trip 30/30, S36), OTA bootstrappé + **JALON C : la monture est pilotée par INDI, end-to-end via le backend REST — Macro 1 bouclée** (S37).
