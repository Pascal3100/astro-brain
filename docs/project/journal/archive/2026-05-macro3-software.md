# Archive journal — Macro 3 Mise en station + GoTo (software) (Sessions 20→25)

Milestone **Macro 3 — Mise en station + GoTo basique**, tranche logicielle (Hub central, wizard d'alignement 3 étoiles, GoTo réel, catalogue backend + page, aide étoile/constellation). Validation matérielle de toutes ces features reportée derrière le déblocage de la liaison monture (Macro 1, fil matériel S26+). Sessions 20→25, du 2026-05-08 au 2026-06-05.

### Session 25 — Macro 3 #2 : aide « étoile dans sa constellation » + chaîne de position (software) (2026-06-05)

Plan `docs/superpowers/plans/2026-06-04-constellation-star-aid.md` (15 tasks) exécuté en mode `superpowers:subagent-driven-development` (implémenteur + double revue spec/qualité par task) sur branche `feat/constellation-star-aid`. Spec : `docs/superpowers/specs/2026-06-04-constellation-star-aid-design.md`. Feature complète « aide à la reconnaissance de l'étoile dans sa constellation » pour le wizard d'alignement.

**Backend** : `constellation_of()` (abréviation IAU dérivée du champ `bayer`) + `visible_stars()` (étoiles d'alignement pointables groupées par constellation) ajoutés à `_alignment_catalog.py` ; asset autonome `astro_brain/data/constellation_figures.json` (23 figures couvrant les 32 étoiles d'alignement) généré une fois par `scripts/build_constellation_figures.py` (sources Stellarium constellationship + HYG, csv non commité) ; loader `services/constellation_figures.py` (figure + matching cible par proximité angulaire + projection alt/az) ; `POST /align/location/client` pour recevoir la position GPS du téléphone, garde 409 sur `/align/start` sans aucune position connue ; `GET /align/constellation/{abbr}` + `GET /align/stars/visible`. **Décision clé** : la chaîne de position devient fix GPS Pi → GPS téléphone → sinon le wizard n'est pas proposé — le fallback Paris codé en dur est supprimé (ADR à consigner si jugé structurant).

**Frontend** : DTOs `ConstellationFigure/Node` ; `AlignmentRepository.fetchConstellation/fetchVisibleStars/postClientLocation` ; widget `ConstellationChart` (CustomPaint, schéma au trait orienté ciel/atlas, étoile cible en halo) ; intégration `per_star_screen` (nom constellation dans le hero + bouton « Voir dans la constellation » → bottom sheet) ; `StarNavigatorScreen` (swap : filtre par constellation **visible** + liste + chart) ; repli position téléphone via `geolocator` (abstraction `PhoneLocation`, fallback 409 dans `AlignmentBloc._onStarted`) ; bandeau « Position GPS requise » sur la carte ALIGNER du Hub quand pas de fix Pi ni position téléphone.

**Tests et incident** : backend 342 passed, app 226 passed, `flutter analyze` clean. TDD strict, double revue par task. Incident notable : l'agent de la dernière task (T14) a timeout avant commit ; travail récupéré et finalisé manuellement — 3 tests Hub réparés (provider `AppBloc` manquant + `pump` vs `pumpAndSettle` + scroll). Validation matérielle (wizard sur ciel réel) reportée derrière déblocage dongle CP2102 (Macro 1).

### Session 24 — Macro 3 #3 GoTo réel + #5 Page Catalogue (software) (2026-06-01)

Plan `docs/superpowers/plans/2026-05-31-catalogue-goto.md` (19 tasks) exécuté en mode `superpowers:subagent-driven-development` (implémenteur + revue spec/qualité par task) sur branche `feat/catalogue-goto`. Brainstorm + spec validés en amont (`docs/superpowers/specs/2026-05-31-catalogue-goto-design.md`, companion visuel pour la mise en page). Feature complète « parcourir le catalogue → pointer ».

**Backend (B1→B9)** : extraction `_ephemeris.py` (conversion RA/Dec→Az/Alt, partagé alignement + catalogue, ré-export depuis `_alignment_catalog.py`) ; `CatalogObject` gagne `altitude_deg`/`azimuth_deg` ; `VisibilityEnricher` (alt/az courants + filtre `visible_now`, dégradation gracieuse sans fix GPS) au-dessus du `CatalogRegistry`, câblé sur `/catalog/objects?visible_now=` via `sensors_bridge.gps_fix` ; `MountService.goto_radec(ra,dec,target_name)` (`ON_COORD_SET=TRACK` + `EQUATORIAL_EOD_COORD`, publie `moving`+`goto_in_progress`+`goto`) ; détection de fin de slew en activant `AstroBrainIndiClient.updateProperty` (no-op jusqu'ici) → `handle_property_update` adapter (EQUATORIAL_EOD_COORD BUSY→Ok/Idle → `ready`+`tracking=sidereal`) ; flag `is_aligned` en RAM (`finalize`→vrai, `cancel`/`invalidate`→faux), publié dans l'état SSE `alignment` ; `AlignmentInvalidator` (abonné bus, invalide à la reconnexion monture `disconnected`/`connecting` — **pas** sur `error` transitoire, fix de revue) ; router `POST /goto` (gardes 409 non-aligné / 409 slew en cours, 422 coords), abort réutilise `POST /stop`.

**Frontend (F1→F10)** : `SystemState` parse le sous-système `alignment` (getters `isAligned`/`gotoInProgress`/`gotoTarget`) ; feature `lib/features/catalogue/` (DTO, `CatalogueRepository`, `CatalogueBloc` recherche debounce + filtres + goto/abort) ; `CatalogueScreen` (bandeau non-aligné + CTA wizard, recherche, chips magnitude/visible-now désactivée sans GPS, liste de cartes, détail en bottom sheet, bouton GoTo grisé si non aligné, slew bar pilotée SSE + STOP) ; carte Hub CATALOGUE + wiring `app.dart`.

**Corrections de revue notables** : `error` retiré des états d'invalidation alignement (un échec de commande INDI transitoire ne doit pas perdre l'alignement) ; `_onGoTo`/`_onAbort` capturent les erreurs → `CatalogueError` (convention codebase) ; `TextField` de recherche extrait dans un widget stateful avec contrôleur (hors `BlocBuilder`) pour ne pas perdre le curseur ; **revue finale (Opus)** a trouvé un défaut masqué par les fakes : `stop_slew(None)` ne réinitialisait pas le latch goto → complétion fantôme `sidereal` après un STOP — corrigé + test de régression.

**Tests** : backend 300 → 322 verts ; app 182 → 196 verts ; `ruff`/`flutter analyze` clean. Validation matérielle (slew réel sur monture) et validation visuelle Android reportées dongle CP2102 (Macro 1).

**Raffinements différés** consignés dans [`../backlog.md`](../backlog.md) (feedback d'échec GoTo en SnackBar, `buildWhen` slew bar, seuil de visibilité par obstruction).

**Validation sur device (Moto g54, Pi déployé à jour, sans dongle)** : le smoke téléphone a remonté plusieurs points, corrigés dans la foulée. (1) **Bug 404 catalogue** : `CatalogueRepository` collait la query dans le path (`/catalog/objects?…`) passé à `getJson` → `PiHost.restUri` faisait `Uri.http(authority, path)` qui encode le `?` en `%3F` → `/catalog/objects%3F…` → 404. Premier endpoint à utiliser une query string ; le test du repo mockait `getJson` sans exercer `restUri`. Fix : query passée via `Uri.http(queryParameters)` + tests de régression `restUri`. (2) **UX cartes** : passage à la version aérée (design B), nom de constellation en toutes lettres (table abréviation IAU → français), bouton POINTER du bottom sheet rendu visible via `SafeArea`. (3) **Filtre par constellation** (menu déroulant client-side, ne liste que les constellations présentes). Aussi : mDNS `astro-brain.local` non résolu par Android → host renseigné en IP dans Setup → Réseau. Tests app 198 → 204. Commits `f179db4`, `b53bde9`, `d51d123`.

### Session 23 — Macro 3 #4 catalogue backend tranche A (stars IAU CSN) (2026-05-10)

Plan `docs/superpowers/plans/2026-05-10-catalog-backend-stars.md` (11 tasks) exécuté en mode `superpowers:subagent-driven-development` directement sur `main`. Tranche A du #4 : pipeline catalogue backend + seed étoiles brillantes IAU CSN cap mag ≤ 3. Tranches Messier + planètes (skyfield) reportées.

**Architecture catalogue** : table sqlite unifiée `catalog_objects` (migration `_003_catalog_objects`, 3 indexes : kind, kind+mag, kind+constellation) ; `CatalogProvider` Protocol + `SqliteCatalogProvider(db, kind=...)` qui requête la table avec filtres `kind`/`search` (sur `name`/`designation`)/`max_mag`, trié par mag puis name ; `CatalogRegistry({"star": provider})` dispatch par kind avec merge+widen pour la pagination cross-kind ; `apply_seeds(db, data_dir)` au boot, lexical glob `seed_*.sql`, idempotent via `INSERT OR REPLACE`, log-and-continue par fichier. Wire dans `astro_brain/app.py` lifespan : `apply_seeds` après `run_migrations` via `as_file(files("astro_brain.data"))`, registry exposé sur `app.state.catalog_registry`.

**Endpoint REST** (`/catalog/objects`) : `GET /catalog/objects?kind=&search=&max_mag=&limit=&offset=` retourne `CatalogListResponse(objects, count, limit, offset)` avec validation Pydantic (limit 1-500, offset≥0, max_mag réaliste). `GET /catalog/objects/{qualified_id:path}` (path converter pour le `:` dans `star:sirius`) → 200 ou 404 `"object not found"`.

**Seed pipeline** : workstation tool `backend/tools/seed_stars.py` télécharge l'IAU CSN (mirror Rochester `pas.rochester.edu/~emamajek/WGSN/IAU-CSN.txt` — l'URL canonique iau.org a été retirée fin 2026), parse le whitespace fixed-width via date-anchored back-parsing (regex `^\d{4}-\d{2}-\d{2}$` localise la colonne 15, puis `date_idx-N` pour récupérer les champs en remontant), filtre V mag ≤ 3.0, sort dans `astro_brain/data/seed_stars.sql` (140 INSERT OR REPLACE déterministes triés par slug). Pipeline déterministe : re-run produit un fichier byte-identique. Ce `.sql` est committé.

**Tests** : 247 → 300 verts (+53). Migration (3), models (3), `SqliteCatalogProvider` (5), `CatalogRegistry` (4), `apply_seeds` (7), routes (6), tool de seed (7), wire app (3), smoke réel (4 : ≥50 stars chargés, Sirius/Vega/Polaris présents avec noms, RA/Dec dans les bornes, filter `max_mag=2.0` retourne ≥10 entrées toutes sous le seuil). Smoke test passe à travers la chaîne réelle (`run_migrations` → `apply_seeds` → `SqliteCatalogProvider`) — il fail loudly si le seed se corrompt.

**Adaptations notables au plan** :
- L'URL canonique `iau.org/.../IAU-CSN.txt` du plan retournait HTTP 403 (site IAU restructuré). Bascule vers le mirror Rochester maintenu par le secrétaire WGSN, autorisée par l'utilisateur en cours de session.
- Plan supposait un format pipe-separated dans la fixture du tool ; le vrai CSN est whitespace fixed-width. Plan Step 3 anticipait la divergence — parser réécrit en date-anchored back-parsing (5 lignes IAU réelles dans la fixture incluant Sirius/Vega/Polaris/Bételgeuse), expected values ajustées sur les vraies données IAU (Sirius mag=-1.45, ra=101.287155, dec=-16.716116, constellation="CMa").
- Code review post-Task-9 : minor off-by-one corrigé (`< 14` au lieu de `< 13` pour le minimum legal `date_idx`) + URL constante `CSN_URL` réalignée sur Rochester (commit polish post-review).
- Tranche A+1 du plan (refactor `wizard_alignment` pour consommer `CatalogRegistry` au lieu de `_alignment_stars.json`) reportée — backlog Macro 3 #2 / #4. `_alignment_catalog.py` reste en place et inchangé pour l'instant.

**Documentation** : roadmap Macro 3 #4 mise à jour (`📦` → `🚧 tranche A livrée 2026-05-10`). Journal : Sessions 17-19 archivées dans `journal/archive/2026-05-macro2-setup.md` (milestone Macro 2 Setup Slices INFRA/A/B/C). Plafond ramené à 4 sessions visibles (20-23).

### Session 22 — Macro 3 #2 wizard 3 étoiles, implémentation software (2026-05-10)

Plan `docs/superpowers/plans/2026-05-09-wizard-3star-alignment.md` (22 tasks) exécuté en mode `superpowers:subagent-driven-development` (implementer + spec reviewer + code-reviewer par task) directement sur `main`. Le wizard va du Hub jusqu'à la validation finale ; restore mid-wizard si une session backend existe.

**Backend** (Tasks T1→T10) : Pydantic models `Star`/`StarRecord`/`AlignmentSession`/`AlignmentModel` (résiduel SVD, `quality` good/marginal/bad), mini-catalogue 30 étoiles brillantes en JSON, `CatalogSelector` (filtrage altitude/séparation), `SvdAlignSolver` (résolution Procrustes orthogonal), repository sqlite `alignment_sessions` (migration `_002_alignment`), `AlignmentService` (machine d'état idle / candidates / pre_pointing / fine_tuning / validating / done), router REST `/align/*` (start, swap, record, restart_star, finalize, cancel) avec 409/422 mappings, wiring dans `build_app`, événement SSE `alignment.session` publié à chaque mutation. Approche défensive : `_publish_session` idempotent, deepcopy du snapshot avant publish.

**Frontend** (Tasks T11→T19) : refactor `DPadControl` API (`onPress: ValueChanged<DPadDirection>` / `onRelease`) et `RateControl` (4 paliers via `ValueChanged<int>`) — préparatoires partagés Manuel/Wizard. DTOs Flutter miroirs des Pydantic, `AlignmentRepository` (REST), `AlignmentBloc` (9 events, 7 states sealed, `existing ?? await repo.start()` pour cold-start restore). Écrans : `IntroScreen` (DÉMARRER), `PerStarScreen` (D-Pad + RateControl + axis bars AZ/ALT + bouton CENTRÉ ✓), `ValidationScreen` (RMS + 3 résiduels barres, bloc diagnostic conditionnel sur outlier `>3× moyenne autres`, REFAIRE/ACCEPTER), `DoneScreen` (RETOUR HUB via `popUntil((r) => r.isFirst)`). Wizard host BlocBuilder route les 7 states. `AstroScreen.alignment` ajouté au enum AppBar. Wire app.dart : `BlocProvider<AlignmentBloc>` (4ème provider) + tuile "ALIGNER" insérée entre MANUEL et SETUP dans le Hub (icône `strokeRoundedTarget02`, hint "3 étoiles · mise en station").

**Adaptations récurrentes au plan** (notées en cours d'exécution) : nom de package `astro_brain` (le plan référençait `astro_brain_app`), `colors.textPrimary` (pas `colors.text`), `text.hudCaption.copyWith()` plutôt que `fontFamily: 'JetBrainsMono'` inline, `bloc_test seed:` (jamais `..emit()`, `@protected`), helper `_wrap` providant AppBloc + ThemeCubit + AlignmentBloc pour les widget tests qui montent l'AppBar. Spec self-contradiction sur les markers d'axis-bars (prose vs Dart de référence) → différée dans `backlog.md`.

**Couverture restante** : T20 cold-start restore — déjà couvert par `existing ?? await repo.start()` + bloc test "WizardStarted resumes existing session" (le plan défère explicitement le dialog visuel "réutiliser modèle finalisé" à Macro 3 #4). T21 ce point. T22 manual integration checklist (validation matérielle reportée derrière dongle CP2102).

**Tests** : app 144 → 180 verts (+36 entre Hub et fin du wizard), backend 191 → 243 verts (+52 sur les 10 tasks backend). `flutter analyze` clean à chaque commit. Validation matérielle reportée Macro 1 INDI.

**Correction architecturale (fin de session, ADR 2026-05-10)** : revue post-implémentation a remonté que le wizard tel que livré construisait un modèle SVD parallèle ignorant l'interface native Celestron, alors que la migration INDI (ADR 2026-05-01) avait été motivée précisément par l'accès à cette interface. Décision : conserver INDI, repositionner le SVD comme indicateur qualité (RMS/résiduels/outlier) et alimenter le modèle natif du driver à chaque record via `MountService.sync_radec(ra_deg, dec_deg)` (`ON_COORD_SET=SYNC` puis `EQUATORIAL_EOD_COORD = (ra/15, dec)`). Patch livré dans la même session : extension `MountService` Protocol, implémentation `MountIndiAdapter.sync_radec` (`set_switch_one_of_many("SYNC")` + push `EQUATORIAL_EOD_COORD`), `FakeMount.sync_radec` enregistre `(ra_deg, dec_deg)` pour testabilité, wire dans `AlignmentServiceImpl.record()` après l'append `StarRecord`. Tests : 3 nouveaux pour l'adapter (sync arme `SYNC`, push RA en heures + DEC en degrés ; erreur si propriété absente ; no-op si device absent), 2 pour le service (3 syncs ordonnés, pas de sync si idx invalide). Backend 248 verts. Spec amendée + checklist enrichie d'un step 10b (validation native Celestron) + roadmap Macro 1 += `sync_radec`, Macro 3 #3 reformulé en `EQUATORIAL_EOD_COORD` + `ON_COORD_SET=TRACK`.

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

**Archive** : Sessions 15+16 (install INDI Pi + backend mount migration) déplacées vers [`2026-05-macro1-indi.md`](2026-05-macro1-indi.md) pour respecter plafond 5-6.

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
