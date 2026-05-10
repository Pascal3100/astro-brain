# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Roadmap restructurée 2026-05-05** : abandon du versioning v0.X, passage à un train de macro-étapes (voir [`roadmap.md`](roadmap.md) + ADR du 2026-05-05). Les sessions antérieures continuent de référencer `v0.X` ; correspondance : v0.1 = Macro 0 Socle, v0.2 = Macro 2 Setup, v0.3 = Macro 3 Mise en station, v0.4 = Macro 4 Catalogue, v0.5 = Macro 5 Caméras, v0.6 = Macro 6 Focus + MES, v0.7 = Macro 7 Astrophoto. La migration INDI devient sa propre Macro 1 (technique).

**Macro 0 — Socle ✅** (livré 2026-04-25) : parité joystick + tracking via app Flutter native. Backend **89 tests** verts (64 socle + 25 migration INDI), app 53 tests. Smoke téléphone Moto g54 5G. Validation physique GPS + compass I2C + network + system ; **monture pas encore branchée** (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` — dongle CP2102 en attente).

**Macro 1 — Migration INDI 🚧**
- ✅ Stack INDI installée sur le Pi (Session 15) : `libindi` 2.2.0 + `indi_celestron_aux` 1.5 + `indi-gpsd` 0.6 via repo Astroberry Trixie arm64. Driver fonctionnel en test isolé (port 7624, plugins SVD + Nearest).
- ✅ Backend INDI atterri sur main (Session 16) : `MountIndiAdapter` + `AstroBrainIndiClient` + helpers + `FakeIndiClient`, `indiserver.service` systemd, script build driver patché, doc bascule. `nexstarpy` retiré du `pyproject.toml`. Patch C++ backlash mount-axis prêt (`/tmp/indi-research/indi-3rdparty/`, commit `538810c`, branche `astro-brain-backlash`).
- ⛔ **Cap suivant** : smoke test E2E sur le Pi (Task 14 du plan migration) — bloque sur la livraison du **dongle USB-TTL CP2102 5V**. Dès que le dongle arrive : câblage HC RJ12, `bash deploy/install.sh`, fork upstream du patch backlash + build sur le Pi, `INTEGRATION_CHECKLIST.md` sections 0+3+Backlash+Cordwrap. Une fois la checklist verte, ouverture du chantier Macro 2 Setup.

**Macro 2 — Setup 🚧** :
- ✅ Carte #8 RÉSEAU livrée (Session 14).
- ✅ Slice INFRA livré (Session 17, 8 commits, +29 tests) — sqlite `state.db` + repos calibration/limits.
- ✅ **Slice A capteurs livré** (Session 18, 2026-05-07) : items #1 niveau monture, #2 compass LIS3MDL, #3 zéro ALT. Fixes review v0.2 (B1, B2, I1-I7, N1-N10) + refactor I8 (`CalibrationBloc` partagé entre les 3 capteurs, -784 LOC). Tests : 178 backend + 115 frontend.
- ✅ **Slice B Courses ALT livré** (Session 19, 2026-05-07) : item #4. Backend `/limits/alt` GET/PUT + écran Flutter capture ALT_min/max via `TiltStreamService`. Tests : 183 backend + 130 frontend.
- ✅ **Slice C About livré** (Session 19, 2026-05-07) : item #9. Backend `GET /about` (versions, IP/SSID, uptime, started_at) + écran Flutter read-only avec bouton RAFRAÎCHIR. Tests : 191 backend + 133 frontend.
- ⛔ Slice D (mount tuning — backlash + cordwrap) bloqué dongle CP2102. Reste à livrer : courses AZ (software, sans hardware) — repoussé à Macro 2 mineure.

**Macro 3 — Mise en station + GoTo basique 🚧** :
- ✅ Item #1 Hub central (Session 20).
- 🚧 Item #2 Wizard alignement 3 étoiles : implémentation software complète (backend + Flutter, 22 tasks plan, Session 22). Validation matérielle bloquée dongle CP2102.
- 📦 Items #3 GoTo réel, #4 Catalogue, #5 Page catalogue.

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12.

## Session en cours

### Session 22 — Macro 3 #2 wizard 3 étoiles, implémentation software (2026-05-10)

Plan `docs/superpowers/plans/2026-05-09-wizard-3star-alignment.md` (22 tasks) exécuté en mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task) directement sur `main`. Le wizard va du Hub jusqu'à la validation finale ; restore mid-wizard si une session backend existe.

**Backend** (Tasks T1→T10) : Pydantic models `Star`/`StarRecord`/`AlignmentSession`/`AlignmentModel` (résiduel SVD, `quality` good/marginal/bad), mini-catalogue 30 étoiles brillantes en JSON, `CatalogSelector` (filtrage altitude/séparation), `SvdAlignSolver` (résolution Procrustes orthogonal), repository sqlite `alignment_sessions` (migration `_002_alignment`), `AlignmentService` (machine d'état idle / candidates / pre_pointing / fine_tuning / validating / done), router REST `/align/*` (start, swap, record, restart_star, finalize, cancel) avec 409/422 mappings, wiring dans `build_app`, événement SSE `alignment.session` publié à chaque mutation. Approche défensive : `_publish_session` idempotent, deepcopy du snapshot avant publish.

**Frontend** (Tasks T11→T19) : refactor `DPadControl` API (`onPress: ValueChanged<DPadDirection>` / `onRelease`) et `RateControl` (4 paliers via `ValueChanged<int>`) — préparatoires partagés Manuel/Wizard. DTOs Flutter miroirs des Pydantic, `AlignmentRepository` (REST), `AlignmentBloc` (9 events, 7 states sealed, `existing ?? await repo.start()` pour cold-start restore). Écrans : `IntroScreen` (DÉMARRER), `PerStarScreen` (D-Pad + RateControl + axis bars AZ/ALT + bouton CENTRÉ ✓), `ValidationScreen` (RMS + 3 résiduels barres, bloc diagnostic conditionnel sur outlier `>3× moyenne autres`, REFAIRE/ACCEPTER), `DoneScreen` (RETOUR HUB via `popUntil((r) => r.isFirst)`). Wizard host BlocBuilder route les 7 states. `AstroScreen.alignment` ajouté au enum AppBar. Wire app.dart : `BlocProvider<AlignmentBloc>` (4ème provider) + tuile "ALIGNER" insérée entre MANUEL et SETUP dans le Hub (icône `strokeRoundedTarget02`, hint "3 étoiles · mise en station").

**Adaptations récurrentes au plan** (notées en cours d'exécution) : nom de package `astro_brain` (le plan référençait `astro_brain_app`), `colors.textPrimary` (pas `colors.text`), `text.hudCaption.copyWith()` plutôt que `fontFamily: 'JetBrainsMono'` inline, `bloc_test seed:` (jamais `..emit()`, `@protected`), helper `_wrap` providant AppBloc + ThemeCubit + AlignmentBloc pour les widget tests qui montent l'AppBar. Spec self-contradiction sur les markers d'axis-bars (prose vs Dart de référence) → différée dans `backlog.md`.

**Couverture restante** : T20 cold-start restore — déjà couvert par `existing ?? await repo.start()` + bloc test "WizardStarted resumes existing session" (le plan défère explicitement le dialog visuel "réutiliser modèle finalisé" à Macro 3 #4). T21 ce point. T22 manual integration checklist (validation matérielle reportée derrière dongle CP2102).

**Tests** : app 144 → 180 verts (+36 entre Hub et fin du wizard), backend 191 → 243 verts (+52 sur les 10 tasks backend). `flutter analyze` clean à chaque commit. Validation matérielle reportée Macro 1 INDI.

Plafond journal atteint (6 sessions visibles : 17→22) — la prochaine session déclenchera une archive `2026-05-macro2-setup.md` (Sessions 17-19 candidates).

### Session 21 — UX fixes post-Hub : propagation offline + libellés FR + nav back (2026-05-09)

Suite directe de Session 20 (Hub mergé). Smoke téléphone a remonté 3 frictions UX, corrigées en mode debug-pose-correctif sur main (pas de feature branch — fixes courts, validés un par un).

**Symptômes** : pastille AppBar "BLEU" clignotant en hors-ligne (label = nom de couleur), Setup card RÉSEAU figée verte Pi injoignable, aucune flèche de retour sur les pages enfants.

**Cause racine identifiée au 4ème commit** : `SplashCubit.continueOffline()` ne dispatchait pas `AppStarted`. L'utilisateur cliquant "Continuer offline" depuis le splash quittait l'écran sans jamais activer la souscription SSE. AppBloc restait en `connecting` initial à perpétuité, aucune erreur ne pouvait remonter puisque rien n'écoutait. Les 3 premiers fix étaient nécessaires mais pas suffisants — leçon : **tracer le chemin event end-to-end avant d'optimiser les sous-couches**.

| # | Commit | Fix |
|---|---|---|
| 1 | `9cdd778` | `EventStreamService._scheduleReconnect` propage `_SseConnectionLost` au stream + Setup card RÉSEAU branchée sur `state.connection` (BlocBuilder) + `AstroAppBar` leading back-arrow conditionnel via `Navigator.canPop()`. Test régression `_FailingClient`. |
| 2 | `a114ae8` | `OverallStatus.displayLabel` getter (FR sémantique : OK / EN COURS / ALERTE / ERREUR / INACTIF / INCONNU). `AstroAppBar` utilise `displayLabel` au lieu de `name.toUpperCase()`. |
| 3 | `246a1d9` | `.timeout(5s)` sur le connect SSE initial. `http.Client.send()` Dart n'a pas de timeout par défaut → blocage indéfini possible si DNS résout sans SYN-ACK (mDNS dans le vide, gateway droppant). |
| 4 | `325e2b6` | **Cause racine** : `SplashCubit.continueOffline()` dispatche maintenant `AppStarted`. La souscription SSE démarre, le timeout frappe, l'erreur propage. |

144/144 verts à chaque commit, `flutter analyze` clean. Smoke téléphone confirmé OK utilisateur.

**Roadmap — retrait courses AZ logicielles** : décision prise en fin de session. L'item "Courses AZ min/max (software)" Macro 2 est retiré du train. Sur cette monture il n'y a pas de butée mécanique en azimut, juste un risque de torsion câbles que le cordwrap (Slice D) gère nativement. La contrainte "ne pas faire de tours inutiles" est reportée sur le path planning du GoTo Macro 3 (ligne amendée). ADR daté 2026-05-09 dans `decisions.md`.

**Archive** : Sessions 15+16 (install INDI Pi + backend mount migration) déplacées vers [`journal/archive/2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) pour respecter plafond 5-6.

### Session 20 — Hub central, Macro 3 item #1 livré (2026-05-08)

Première étape de la Macro 3. Mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task). Branche `feat/macro3-hub-central` partie de `de454e4`.

**Décision design** : Hub évolutif (pas anticipateur). Le Hub n'affiche que les features vivantes ; pas de cartes "Coming soon". Chaque feature livrée ajoute sa carte au moment d'arriver. Stratégie validée en brainstorm contre une variante "anticipative" qui aurait pré-affiché Wizard / GoTo / Catalogue grisés.

**Refactors préliminaires** (Tasks 1-4 — commits `826b586` → `22b45b9`)

- Enum `AstroScreen` étendu : ajout `hub`, `manual` (transitionnel), puis `about`. Suppression `home`. Ordre final : `hub, manual, system, setup, about`.
- `features/home/` → `features/manual/` (rename complet : `HomeScreen` → `ManualScreen`, `HomeBloc` → `ManualBloc`, events/states/widgets).
- `features/setup/about/` → `features/about/` : About sort de Setup, devient feature racine accessible directement depuis le Hub. Setup passe de 9 à 8 cartes.
- Tests adaptés à chaque renommage. 31 → 143 verts à chaque étape, `flutter analyze` clean.

**Task 5 — `HubCard`** (commit `bfe759b`) — TDD 3 tests (rendu, tap, primary chevron). Hero icon HugeIcons (28 px) + label JetBrains Mono + hint Inter + chevron Phosphor. Variant `primary` : gradient accent + glow. **Bug plan corrigé en cours d'exécution** : `hugeicons 1.1.6` expose ses icônes comme `static const List<List<dynamic>>` rendues via `HugeIcon(icon: …)`, **pas comme `IconData`**. Plan amendé inline (Tasks 5 et 6) ; tests adaptés à `find.byWidgetPredicate` au lieu de `find.byIcon`.

**Task 6 — `HubScreen`** (commit `4c0b142`) — TDD 7 tests (4 cartes en ordre, primary, header, 4 navigations). `StatelessWidget`, `ListView.separated` de 4 `HubCard`, AstroAppBar(current: hub), header `// ASTRO-BRAIN` + question `Que fait-on ce soir ?`. Adaptations test-side : ajout `BlocProvider<ManualBloc>` au wrap (ManualScreen le réclame via context), remplacement `pumpAndSettle()` par `pump() + pump(400ms)` dans les tests de navigation (les destinations Setup/About ont des Futures async qui ne settlent jamais sous test).

**Code review feedback** (commit `dfcdc1b`) : remplacement d'un `TextStyle(fontSize: 18, …)` inline pour le sous-titre par `Theme.of(context).textTheme.titleMedium?.copyWith(...)` — laisse le design system contrôler la taille et la famille.

**Task 7 — wire root** (commit `72be076`) — `app.dart::_RootRouter.build` retourne `const HubScreen()` au lieu de `const ManualScreen()`. Splash → Hub par défaut.

**Dépendance ajoutée en parenthèse** : `hugeicons: ^1.1.6` pour fournir le vocabulaire astro (telescope, satellite, radar, orbit, constellation…). Convention double set documentée dans `design-system.md` : Phosphor reste pour l'UI utilitaire (chevrons, gear, info), HugeIcons exclusivement pour les hero icons domaine (cartes Hub, splash, headers de feature).

**Validation Android USB** : à faire — pas exécutée par les subagents (validation visuelle reportée à l'utilisateur). Tests automatisés OK : 143/143 verts, `flutter analyze` clean.

### Session 19 — Macro 2 Setup, Slices B + C livrés (2026-05-07)

Enchaîne directement après Session 18 (Slice A mergé + Pi mis à jour). Mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task). Branche `feat/v02-setup-limits` partie de `378dc93`.

**1. Task B-1 — backend `/limits/alt`** (commit `8a301ff`)

`GET /limits/alt` → 200 `AltLimits` ou 404 `"alt limits not set"` ; `PUT /limits/alt` body validé via `AltLimits._check_range` (min<max + écart≥30) → 422 auto sur invalide, sinon 200 + echo du payload sauvé. Route câblée sur `Depends(deps.get_db)` + `repository/limits_repo` (déjà livré INFRA-4) — zéro SQL dans la route. TODO `v0.3: clamp slew("alt", "+") near max_deg` posé dans `mount_indi_adapter.slew()` pour mémoire (pas d'implémentation v0.2). 5 tests via `TestClient` (`:memory:` DB + migrations réelles, pas de mocks). Backend : 178 → 183 verts.

**2. Task B-2 — écran Flutter Courses ALT** (commit `c927b63`)

`AltLimits` Dart placé dans nouveau `app/lib/models/limits.dart` (séparé de `calibration.dart` — limits ≠ calibration). `ApiService` étendu : `getAltLimits()` retourne `null` sur 404 (cas non-calibré, normal), `putAltLimits(limits)` propage `ApiException` sur 422.

`LimitsAltBloc` minimal : 4 events (`Reloaded`, `LowerCaptured(altDeg)`, `UpperCaptured(altDeg)`, `SaveRequested`), state avec sentinels pour distinguer "non capturé" de "set à null", computed `canSave` (les deux non-null + écart≥30 + pas en cours de save) et `hasRangeWarning`. Re-capture override sans reset l'autre borne (arbitrage simplicité).

Écran : `TiltStreamService` ouvert en `initState` (5 Hz), gros affichage ALT live (48 px) au centre. Boutons "POINTER LE PLUS BAS" / "POINTER LE PLUS HAUT" → snapshot `pitchDeg` (le `TiltReading` n'a pas de champ `altDeg`, mais `adxl_tube_screen.dart` faisait déjà la même équivalence pitch=ALT). Après capture, le bouton se transforme en "✓ ALT_min capturé : -3.2°" (background `surfaceContainerHighest`, opacité 0.4). Bouton ENREGISTRER `FilledButton` avec spinner pendant `isSaving`. Sur 200 → snackbar succès + `Navigator.pop(true)` ; sur 422 → message inline "Plage invalide". Warning ⚠ "Plage trop faible" inline si les deux captés et écart < 30°.

Carte parent (`setup_screen.dart` #4) : `_placeholder` remplacé par `FutureBuilder<AltLimits?>` avec compteur `_limitsAltRefresh` ré-incrémenté au `pop(true)`. Sublabel "min Xx° / max Yy°" si set, "Non défini" sinon. Dot vert / gris.

Tests Flutter : 115 → 130 verts (10 bloc + 5 api_service). `flutter analyze` clean.

**3. Code review (synthèse)**

Spec compliance ✅ pour les deux tasks. Code-reviewer ✅ pour les deux ; aucun blocker. Notes laissées pour follow-up (non-bloquantes) :
- B-1 : 4 minors purement polish (phrasing 404, layering hint dans le TODO, fixture async sync).
- B-2 : 7 findings dont 2 "Important" explicitement défendables (double subscription au stream broadcast — défensible par perf rebuild ; `fontSize: 48` hardcodé — premier "centerpiece readout" du projet, mériterait un token `hudDisplay` à terme). Pattern `_xRefresh` int counter en train de devenir un smell (4 occurrences sur 9 cartes) — abstraction `RefreshableCard` à envisager quand on aura #5/#6/#7/#9.

**4. Merge Slice B sur `main`**

`git merge --no-ff feat/v02-setup-limits` (commit `2f49ad4`). Branche conservée. Push à venir avec Slice C ou en standalone selon la suite.

**5. Slice C — About (item #9)** — enchaîné dans la même session

Branche `feat/v02-setup-about` partie de `3991569`. Mêmes outils (subagent-driven-development).

**Task C-1 — backend `GET /about`** (commits `789539a` + `f402aa8`)

`AboutResponse` Pydantic à 7 champs (`backend_version`, `app_version_seen`, `mount_firmware`, `ip`, `ssid`, `uptime_s`, `started_at`). `__version__ = "0.2.0"` ajouté dans `astro_brain/__init__.py`. `app.state.started_at = datetime.now(UTC)` set au lifespan startup.

Pour exposer IP/SSID et uptime sans bloquer la route sur du I/O subprocess, ajout d'une méthode synchrone `current_snapshot()` sur `NetworkInfoAdapter` + `SystemInfoAdapter` (et leurs fakes), promue au protocole dans `services/interfaces.py`. Lecture du dernier `_last` cache, pas d'appel à `ip`/`iwgetid`. Pré-start guard : retourne `{"ip": None, "ssid": None}` ou `{"uptime_s": None}` si `start()` pas encore tourné — défensif inoffensif (lifespan termine avant requête).

`mount_firmware` : laissé à `None` en v0.2 avec TODO "extract from MountIndiAdapter when INDI is stable (post-Macro 1)" — éviter de rouvrir la boîte INDI maintenant. `app_version_seen` : `null` v0.2 (header `X-App-Version` pas encore consommé). 8 tests via `build_app(use_hardware=False, db_path_override=":memory:")` + `TestClient` (lifespan exécuté → `started_at` réel). Backend 183 → 191 verts.

Fix code review : variable locale `sys` shadowait le module stdlib (pas de bug actuel mais réflexe d'hygiène) → renommée `sys_snapshot` dans un commit séparé `f402aa8`.

**Task C-2 — écran Flutter À propos** (commit `b0fc051`)

Modèle `AboutInfo` (Equatable, fromJson) dans `models/about.dart` — tous les champs nullable sauf `backendVersion`. `ApiService.getAbout()` GET → 200 ou throw. Bloc minimal : 2 events (`AboutLoaded`, `AboutRefreshRequested`) qui partagent un même handler `_onFetch` (DRY), state `(info, isLoading, errorMessage)` avec sentinels `copyWith` consistants avec `LimitsAltState`.

Choix `kAppVersion = '1.0.0+1'` constante en dur dans `app/lib/version.dart` plutôt que `package_info_plus` runtime — déviation explicite du plan validée à l'amont (YAGNI : pas envie d'ajouter une dep pour une string, et `pubspec.yaml` est la source de vérité). Doc-comment dans `version.dart` rappelle de re-sync à chaque bump pubspec.

Écran : `AstroAppBar` + 3 `HudPanel` sectionnés (VERSIONS / RÉSEAU / SYSTÈME), chaque tuple via `_InfoRow(label, value)` avec fallback `value ?? '—'`. `_formatUptime` (s → "Xj Yh" / "Xh Ym" / "Xm Ys") et `_formatStartedAt` (parse ISO 8601 → local datetime, try/catch fallback raw string). Bouton RAFRAÎCHIR (`FilledButton` avec spinner pendant `isLoading`) dispatch `AboutRefreshRequested`. Banner d'erreur inline (`buildWhen` sur `errorMessage`).

Carte parent (`setup_screen.dart` #9) : `_placeholder(9, …)` remplacé par `_buildAboutCard()` avec `FutureBuilder<AboutInfo>` keyé sur `_aboutRefresh`. Sublabel `'v${info.backendVersion}'` quand 200, dot vert ; gris/`'—'` sinon. `_openAbout()` toujours `_aboutRefresh++` au retour (intentionnel : la version backend peut changer après un restart).

Tests Flutter : 130 → 133 verts (3 bloc tests : happy 200, error 500, recovery refresh-after-error). `flutter analyze` clean.

**6. Code review Slice C (synthèse)**

Spec compliance ✅ pour les deux tasks. Code-reviewer ✅ pour les deux ; aucun blocker. Notes laissées :
- C-1 : 7 minors (idiomatic `datetime` vs `str` pour `started_at`, fixture pytest pour mutualiser `build_app`, defaults Pydantic non-load-bearing, etc.) — tout polish.
- C-2 : 7 findings dont 5 minors, 0 critique, 0 important. `as String` non-gardé sur `backendVersion` (acceptable, le contrat C-1 garantit la string), `_aboutRefresh` toujours incrémenté (intentionnel, doc'd), `SizedBox(width: 140)` magic number (à tokeniser plus tard).

Pattern `_xRefresh` int counter persiste à 5 occurrences (1/2/3/4/9) — abstraction `RefreshableCard` confirmée comme follow-up Macro 3 quand on aura encore plus de cartes.

**7. Merge Slice C sur `main`**

`git merge --no-ff feat/v02-setup-about` (commit `06056d7`).

**8. Bilan Macro 2**

Items #1, #2, #3, #4, #8, #9 livrés. Reste :
- 📦 Courses AZ (software, déférable — pas hardware-dependent mais marginal en utilité tant qu'on n'a pas de monture branchée).
- ⛔ Backlash ALT + AZ (#5, #6) + Cordwrap (#7) — Slice D, bloqué dongle CP2102. Sans ces trois cartes, la Macro 2 n'est pas "done" au sens roadmap (alignement sérieux possible) mais le télescope reste utilisable end-to-end via Slices A/B/C en attendant.

Macro 2 effectivement **80% livrée** ; reprise après livraison du dongle.

### Session 18 — Macro 2 Setup, Slice A capteurs livré + refactor I8 (2026-05-07)

Suite directe de Session 17 (Slice INFRA mergé). On enchaîne le Slice A capteurs (LIS3MDL + ADXL345 ×2) sur la branche `feat/v02-setup-sensors`, mode `superpowers:subagent-driven-development`. Slice livré dans la session précédente, cette session fait le code review, les fixes, le merge, puis sort un refactor dédié pour collapser les 3 blocs Flutter.

**1. Code review `superpowers:code-reviewer` sur `feat/v02-setup-sensors`**

Verdict : ✅ approuvé avec corrections. Aucun blocker ; ~20 findings classés. Tout ce qui est concret a été appliqué :

| Tag | Sujet | Commit |
|---|---|---|
| B1 | `setState` manquant à l'init du `TiltStreamService` côté écran tube → preview ALT silencieusement noir | `863a4bb` |
| B2 | Idempotence du `POST /calibration/.../start` : un double-clic doublait la session backend → check `current_session is not None` | `f4ed8d1` |
| I1 | Formule heading tilt-compensé alignée sur l'AN-203 (rotation accel d'abord, projection mag ensuite) — l'ancien ordre divergeait à >5° d'inclinaison | `f4ed8d1` |
| I2 | `logger.exception` partout dans `calibration_service` (état `error` était diagnostiqué uniquement via stack trace fugace) | `f4ed8d1` |
| I3 | Race start/lock — `asyncio.Lock` autour de `start_session` pour fermer la fenêtre entre `current_session is None` et l'écriture | `f4ed8d1` |
| I4 | `calibration_repo.list_sensors()` tolère désormais une row corrompue (skip + warn) plutôt que de crasher la liste entière | `f4ed8d1` |
| I5 | `CalibrationProgress` snapshot deep-copié avant publish SSE (mêmes raisons que `active_slews` Session 16) | `f4ed8d1` |
| I6 | Fakes ADXL345/LIS3MDL consolidés dans `tests/fakes/` (3 copies divergentes → 1 source) | `c112b97` |
| I7 | Stream `/sensors/tilt` & `/sensors/compass` : 422 si `hz` hors borne au lieu de clamp silencieux | `f4ed8d1` |
| N1 | `urlencode` manquant sur `sensorId` dans `api_service.dart` | `863a4bb` |
| N6 | `mountCalibrated=null` (pas `false`) sur erreur de chargement Setup pour distinguer "absent" de "non chargé" | `863a4bb` |
| N2-10 | Nits divers (constantes seuils extraites, naming, doc inline) | `f4ed8d1` / `863a4bb` |

Tous les tests verts à chaque étape : 178 backend + 124 frontend.

**2. Merge Slice A sur `main`** (commit `28ba9d8`)

Branche `feat/v02-setup-sensors` mergée fast-forward. Push `origin/main`. La page Setup expose maintenant les cartes #1 #2 #3 en `📦 → ✅` côté roadmap.

**3. Refactor I8 — `CalibrationBloc` partagé** (branche `refactor/calibration-bloc-base`, commits `cdc3b85` puis merge `ea087c0`)

Code review I8 (laissé deferred au merge slice) : les 3 blocs Flutter (`adxl_mount_bloc`, `adxl_tube_bloc`, `lis3mdl_bloc`) étaient quasi-identiques — seul le `sensorId` et la fonction de gating diffèrent. Décision arbitrée avec l'utilisateur : pas de génériques `CalibrationBloc<TPayload>`, simple injection :

```dart
CalibrationBloc(
  api: api,
  sensorId: 'adxl345_mount',                // ou tube / lis3mdl
  finalizeGate: adxlCanFinalize,            // ou lis3mdlCanFinalize
  progressStream: (id) => ...               // factory injectée
)
```

Gates en top-level dans `calibration_bloc.dart` :
- `adxlCanFinalize` : `samplesN >= 100 && sigma < 0.05`
- `lis3mdlCanFinalize` : `samplesN >= 500 && coveragePct >= 80.0`

État du bloc : on réutilise l'enum `CalibrationState` (`idle/sampling/computing/done/aborted/error`) déjà exporté par `models/calibration.dart` — pas de doublon `CalibrationPhase`. Pour éviter le clash de noms avec la classe d'état du bloc, celle-ci s'appelle `CalibrationBlocState`. Le bloc réexporte `CalibrationState`/`CalibrationStatus`/`CalibrationProgress` pour que les écrans n'aient qu'un seul import.

`finalizeGate` est stocké dans l'état mais hors `props` Equatable (callback constant pour un bloc donné, n'a pas d'incidence sur l'égalité). 12 fichiers supprimés (3× bloc + event + state + test), 2 fichiers ajoutés (`calibration_bloc.dart` + `calibration_bloc_test.dart`), 3 écrans migrés. Net : **-784 LOC** (648 ins / 1432 del).

Tests Flutter : 124 → 115 (suppression des doublons par-capteur, on garde happy paths ADXL + LIS3MDL, abort, 409 start, SSE end pendant sampling, gates indépendantes, fromJson sanity).

Merge sur `main` (`ea087c0`) + push.

**4. Déploiement Pi (premier déploiement post-Session-14)**

Le Pi tournait encore sur `feat/mount-indi @ adf7f5e` (Session 14, 3 mai) — d'où les 404 sur `/calibration/*` quand l'app a tenté les écrans Slice A. Mise à jour menée depuis main :

- `git checkout main && git pull --ff-only` → fast-forward 99 commits (Sessions 15→18 atterrissent sur le Pi en un coup).
- `uv sync --extra hardware` (3 min 26 s) : `nexstarpy` + `pyserial` retirés ; `pyindi-client 2.2.0`, `numpy 2.4.4`, `smbus2 0.6.1`, `aiosqlite 0.22.1` installés.
- Premier crash au restart : `PermissionError: '/var/lib/astro-brain'`. L'unit systemd installé sur le Pi datait aussi de Session 14 — il manquait `StateDirectory=astro-brain` (livré INFRA-6). Côté repo, l'unit à jour (Session 17) + `indiserver.service` (Session 16) n'avaient jamais été poussés vers `/etc/systemd/system/`.
- `sudo cp` des deux units → `daemon-reload` → enable+start `indiserver.service` → restart `astro-brain.service`.
- Vérifs : `/var/lib/astro-brain/state.db` créé (24 KB, ownership `pascal3100`), tous endpoints calibration en 200, app Flutter à nouveau fonctionnelle pour les 3 écrans Slice A.
- `mount=error` attendu (indiserver up mais driver `indi_celestron_aux` sans port série tant que le dongle CP2102 n'est pas livré) — sans incidence sur les capteurs I2C.

À retenir pour les prochains déploiements : quand un slice modifie un unit systemd (`backend/deploy/*.service`), le `git pull` ne suffit pas — il faut `sudo cp` + `daemon-reload`. Le `INTEGRATION_CHECKLIST.md` couvre ça mais on l'a sauté en pull "rapide".

**5. Reste pour Macro 2**

- Slice B (courses ALT, 2 tasks) — pur logic backend + écran simple, ouvrable sans hardware.
- Slice C (à propos, 2 tasks) — versions/IP/redémarrage, ouvrable sans hardware.
- Slice D (mount tuning backlash + cordwrap) — toujours bloqué dongle CP2102.

**6. Méta**

Sessions 11-14 archivées dans [`journal/archive/2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) (milestone : préparation v0.2 Setup — brainstorm, doc tree, recherche protocole NexStar, scaffold #8 Réseau). Journal courant : Sessions 15-19 (5 sessions, sous le plafond).

### Session 17 — Macro 2 Setup, Slice INFRA livré (2026-05-05)

Suite directe du restructuring roadmap (commit `c9b188b`, abandon v0.X → train de macro-étapes). Macro 1 INDI reste bloquée par le dongle CP2102 ; Slice INFRA Macro 2 (backend pur logic, pas de hardware) est indépendant — on l'attaque pour avancer pendant l'attente.

**Mode d'exécution** : `superpowers:subagent-driven-development` — fresh implementer par task + double review (spec compliance puis code quality), sur branche `feat/v02-setup-backend-infra`.

**8 tasks INFRA livrées** (89 → 118 tests verts) :

| # | Commit | Sujet |
|---|---|---|
| INFRA-0 | `e3e770f` | deps `aiosqlite` + `numpy` core, `smbus2` extra hardware |
| INFRA-1 | `1c3b2bd` | Pydantic models calibration (Adxl345/Lis3mdl/AltLimits/CalibrationProgress/CalibrationStatus) |
| INFRA-2 | `a70f164` | aiosqlite repository scaffolding + migration `_001_initial` (3 tables) |
| INFRA-2-fix | `7f35dac` | simplification de la discovery migration (single source = `module.VERSION`) + drop try/rollback redondant |
| INFRA-3 | `070baac` | `calibration_repo.py` (CRUD typé + validation cross-type sensor↔payload, TypeError) |
| INFRA-4 | `4e0c05a` | `limits_repo.py` (CRUD ALT, axis hardcoded) |
| INFRA-5 | `e3de355` | wire DB lifecycle dans `app.py` (`db_path_override` kwarg) + `deps.get_db` |
| INFRA-6 | `1c38f3d` | systemd `StateDirectory=astro-brain` + `ASTRO_BRAIN_STATE_DIR` + checklist DB persistante |
| INFRA-7 | `f624d5d` | docs architecture + state-model — sqlite + calibration off-bus |

**Décisions notables prises pendant le slice** :
- `db_path_override` (et pas `db_path`) en paramètre de `build_app` pour ne pas masquer la fonction importée du même nom.
- `axis="alt"` hardcodé dans `limits_repo` ; pas de paramètre `axis` (YAGNI — on l'ajoutera si Macro 3 ajoute `azm`).
- `TypeError` (et non `ValueError`) pour le mismatch sensor_id ↔ payload dans `calibration_repo` — sémantique correcte vs sensor_id inconnu (`ValueError`).
- Ordre lifespan : DB up first / DB down last (futur-proof si un service vient à dépendre de `app.state.db`).
- Tests `test_app.py` migrés vers `db_path_override=":memory:"` pour éviter de toucher `/var/lib/astro-brain` en CI/workstation.

**Reste pour Macro 2** : Slice A (capteurs LIS3MDL + ADXL345 ×2, ~13 tasks), Slice B (courses ALT, 2 tasks), Slice C (about, 2 tasks), Slice D (mount tuning — backlash + cordwrap, **bloqué dongle**). Branche `feat/v02-setup-backend-infra` non encore mergée sur `main` ni poussée.

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
- [`2026-04-frontend-v0.1.md`](journal/archive/2026-04-frontend-v0.1.md) — Sessions 8→10 : démarrage app Flutter (thème + design system), livraison v0.1 (Splash / Home / System, blocs, services REST + SSE, 47 tests), smoke test Moto g54 5G + 4 fixes UX (53 tests).
- [`2026-04-v02-setup-prep.md`](journal/archive/2026-04-v02-setup-prep.md) — Sessions 11→14 : préparation v0.2 Setup — brainstorm v0.2, réorganisation roadmap + arborescence docs en 3 vues, recherche exhaustive du protocole NexStar + assainissement repo, scaffold Flutter + carte #8 Réseau livrée.
- [`2026-05-macro1-indi.md`](journal/archive/2026-05-macro1-indi.md) — Sessions 15→16 : install stack INDI 2.2.0 + driver Celestron AUX sur le Pi (Astroberry Trixie arm64), rebase + merge backend `MountIndiAdapter` + `pyindi-client` sur main (89 tests verts, `nexstarpy` retiré). Smoke test E2E reste bloqué par dongle CP2102.
