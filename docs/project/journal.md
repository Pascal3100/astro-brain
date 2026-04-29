# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. **Plafond : 5-6 sessions max ici** ; au-delà, on archive par milestone dans `journal/archive/`.

## État du projet

**Version active** : `v0.1 livrée` — parité joystick + tracking avec la raquette Celestron via app Flutter native. Backend (64 tests) et app (53 tests) sur main. Smoke test téléphone fait sur Moto g54 5G. Validation physique faite sur **GPS + compass I2C + network + system** ; **monture pas encore branchée** (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` à dérouler — connecteurs en attente).

**Cap suivant** : `v0.2 = Setup` (calibration capteurs, courses, backlash, network/IP, à propos). Le wizard de mise en station + GoTo + catalogue passent en v0.3 : on ne peut pas aligner sérieusement sans calibration capteurs.

**Brainstorm en cours** : v0.2 Setup. Décisions hub/AppBar/catalogue backend prises pendant la session 11, à recoller au scope Setup à la prochaine reprise.

**Doc tree** : nouvelle arborescence `docs/INDEX.md` → 3 vues (`technical/`, `project/`, `product/`). Petits docs ciblés, navigation par liens. Voir Session 12 pour le rationale.

## Session en cours

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

### Session 10 — smoke test sur téléphone + 4 fixes UX (2026-04-25)

Smoke test Step 14.4 du plan v0.1 app déroulé sur Moto g54 5G. Pour contourner un souci réseau Bbox (workstation joint le Pi mais pas le téléphone, malgré même BSSID 5 GHz), montage d'un workaround **tunnel SSH `localhost:8000` → Pi + `adb reverse tcp:8000`** : le téléphone voit le backend comme `localhost:8000`. Pour rendre l'override propre, `PiHost` accepte maintenant `--dart-define=PI_HOST=...` / `--dart-define=PI_PORT=...` (défaut `astro-brain.local:8000`).

Backend live : MOUNT en `error` (ttyUSB0 absent, normal — connecteurs pas encore arrivés), GPS `fix_3d` 16 sats, NETWORK + SYSTEM verts. Tracking observable côté Pi via `journalctl -u astro-brain.service -f` (POST /slew, /stop, /tracking arrivent bien).

**4 remarques relevées au fil → 4 fixes appliqués** :

1. **Splash → Home trop bref / ghost screen** : `SplashCubit` accepte un `minPhaseDuration` (défaut 350 ms). Chaque phase s'affiche au moins ce délai. Total ~1 s minimum au lieu d'un flash.
2. **D-Pad sans feedback au press** : `_Btn` en `StatefulWidget` avec état `_pressed` + `AnimatedContainer` (`motionFast` 120 ms). Au tap-down : `Color.lerp(bg, accent, 0.32)` + bordure `strokeBold` + `BoxShadow(accentGlow, blur 16)`.
3. **Message d'erreur MOUNT trop technique** (`[Errno 2] could not open port…`) : nouvelle util `humanizeMountMessage(String?)` dans `lib/utils/mount_error_messages.dart` qui matche 3 patterns connus + fallback. Appliqué uniquement côté affichage SystemScreen — les logs serveur restent techniques. 6 tests sur le humanizer.
4. **Toggle tracking cliquable malgré mount=error** : `disabled = !connected || mount.state ∉ {ready, moving}`. `buildWhen` reconstruit aussi sur `mount.state`.

**Tests** : 47 → 53 verts (+6 sur le humanizer, +0 régression). `flutter analyze` clean.

**Reste smoke test** : test offline (`adb reverse --remove tcp:8000` + couper le tunnel SSH) → vérifier pastille offline + bouton reconnect. Investiguer isolation client Bbox sélective Pi↔téléphone.

### Session 9 — app Flutter v0.1 livrée (2026-04-24)

Exécution du plan `docs/superpowers/plans/2026-04-24-astro-brain-v01-app.md` en mode subagent-driven, 17 tâches enchaînées. Résultat : 3 écrans fonctionnels, toute la mécanique REST + SSE + état global en place.

**Écrans livrés** :
- `SplashScreen` — 3 phases séquentielles, fallback avec bouton "continue offline" et icône Phosphor `planet`.
- `HomeScreen` — gradient bg, `StatusBar` (pastille + toggle thème + reconnect conditionnel), `DPadControl` 3×3, `RateControl` (9 barres + boutons ±), `TrackingToggle` (Switch + libellé, grisé si déconnecté).
- `SystemScreen` — 5 `SubsystemCard` (MOUNT / GPS / TRACKING / NETWORK / SYSTEM), chacune avec icône, libellé, détails contextuels, `depuis Xs/Xmin/Xh`, pastille `GlobalDot`, message d'erreur optionnel.

**Blocs / Cubits** :
- `AppBloc` — `(system: SystemState?, connection: ConnectionStatus)`. Expose `effectiveOverall` (pastille globale = max des 5 sous-systèmes + statut connexion).
- `HomeBloc` — `rate` 1..9 (clamp), event `HomeSlewPressed/Released` → `ApiService.slew/stop`, `HomeTrackingToggled` → `ApiService.setTracking`. try/catch + `lastError`.
- `SplashCubit` — orchestre `fetchState` → `appBloc.add(AppStarted)` → `success` ; `failure` + `continueOffline()`.
- `ThemeCubit` — `AstroThemeMode { day, night }`, persistance `shared_preferences` (clé `astro.theme.mode`).

**Services** :
- `ApiService` — REST sur `astro-brain.local:8000`, timeout 3 s, `fetchState/slew/stop/setTracking`. Erreurs HTTP → `ApiException`.
- `EventStreamService` — client SSE par-dessus `http.Client.send()`, broadcast `Stream<SystemState>`, reconnexion auto avec backoff `[1s, 2s, 4s, 10s]`. Distinction `stop()` / `dispose()` (reconnect manuel).
- `SseParser` — parse incrémental (event/data/commentaires/multi-lignes/split mid-ligne).

**Modèles** : `SubsystemState<T>` générique, `SystemState` avec `fromJson` (snapshot) et `applyUpdate` (patch incrémental SSE). `OverallStatus { green, blue, orange, red, offline }` + 5 enums sous-systèmes (parse tolérant aux minuscules).

**Racine app** : `lib/app.dart` — `AstroBrainApp({required SharedPreferences prefs})` avec `MultiRepositoryProvider`, `MultiBlocProvider`, `MaterialApp` pilotée par `ThemeCubit`, `_RootRouter` qui flip un `_ready` bool quand le splash finit.

**Tests** : 47/47 verts. Modèles, `SseParser` (5 cas), `ApiService` (5 cas avec `http.MockClient`), `EventStreamService` (2 cas), `AppBloc` (2 blocTest), `HomeBloc` (3 blocTest), `SplashCubit` (2 blocTest), `ThemeCubit` (3 cas).

**Hors scope v0.1** : configuration manuelle d'IP/port, mode hotspot Pi, mDNS fallback, smoke test téléphone (déplacé en Session 10).

**Contraintes rencontrées** :
- Collision de nom `Axis` (Flutter `dart:ui` vs notre enum) — résolu par `import 'package:flutter/material.dart' hide Axis;`.
- `PhosphorIconsBold.telescope` n'existe pas en 2.1.0 — substitué par `planet`.
- `google_fonts` fait un fetch HTTP au premier usage : tests `AstroTheme.buildDay()` toujours hors suite.

**Commits** : 17 commits entre `16d38eb` (baseline) et `fceec5e` (Task 16 reconnect manuel).

### Session 8 — démarrage app Flutter v0.1, thème + design system (2026-04-24)

Attente des connecteurs monture → on ouvre le chantier app Flutter en parallèle. Choix d'archi : **pattern BLoC** (MVVM-like) via `flutter_bloc`, bible officielle `docs.flutter.dev`. Noté en mémoire persistante.

Scaffold Flutter dans `app/` (Flutter 3.41.6 / Dart 3.11.4). Dépendances : `flutter_bloc`, `equatable`, `google_fonts` (Inter + JetBrains Mono), `phosphor_flutter`.

**Design system posé en 5 fichiers sous `lib/theme/`** :

- `design_tokens.dart` — constantes brutes (couleurs jour/nuit, échelle d'espacement base 4, rayons, durations, tailles d'icônes).
- `app_colors.dart` — `AppColors` en `ThemeExtension<AppColors>` : slots sémantiques que M3 n'a pas (`accent`, `accentGlow`, `bgGradientTop/Bottom`, `grid`, `textPrimary/Muted`, `dotOk/Transition/Warn/Error`). Deux instances `const` : `AppColors.day` (bleu spatial) et `AppColors.night` (rouge astro, aucun bleu ni vert). Extension `context.colors`.
- `app_typography.dart` — `buildInterTextTheme(color:)` pour `TextTheme` M3 ; `AppTextStyles` en `ThemeExtension` pour styles HUD monospace JetBrains Mono. Extension `context.textStyles`.
- `astro_theme.dart` — `AstroTheme.buildDay()` / `buildNight()` : `ThemeData` M3, `Brightness.dark` pour les deux, `ColorScheme` mappé sur tokens, themes pour `FilledButton`, `OutlinedButton`, `Card`, `AppBar`, `Divider`, `IconTheme`. `ThemeExtensions` injectées via `extensions:`.
- `theme_cubit.dart` — `ThemeCubit extends Cubit<AstroThemeMode>`.

**`main.dart`** : `AstroBrainApp` racine expose `BlocProvider<ThemeCubit>` + `BlocBuilder` qui choisit `ThemeMode.light`/`dark` → `MaterialApp.theme`/`darkTheme`. Page provisoire `_ThemePreviewScreen` valide visuellement tous les tokens.

**Vérifications** : `flutter analyze` clean. `flutter test` 5/5 verts (AppColors × 2, ThemeCubit × 3). Tests qui instancient `AstroTheme.buildDay()` absents : `google_fonts` tente un fetch HTTP qui foire en sandbox sans réseau. À réactiver quand on bundlera les TTF en assets.

**Pattern d'accès aux tokens** :
```dart
final colors = context.colors;        // AppColors (ThemeExtension)
final text = context.textStyles;      // AppTextStyles (ThemeExtension)
DesignTokens.spaceLG;                 // constante brute
```
Aucun `Color(0xFF...)` ne devrait apparaître hors de `design_tokens.dart`. Aucun `GoogleFonts.inter(...)` hors de `app_typography.dart`.

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→7 : brainstorm, spec design, monorepo + uv, Tasks 1-17 du plan backend, revue/renforcement, validation physique GPS + compass, décision capteurs ADXL345.
