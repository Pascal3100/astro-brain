# Archive — Frontend v0.1 (avril 2026)

Sessions 8 à 10. Période couverte : démarrage du chantier app Flutter (en parallèle de l'attente des connecteurs monture), exécution du plan v0.1 app, smoke test sur Android physique + 4 fixes UX issus du smoke test. Clôture du milestone **app v0.1** : 3 écrans fonctionnels (Splash / Home / System), 53 tests verts, parité joystick + tracking avec la raquette Celestron.

## Session 8 — démarrage app Flutter v0.1, thème + design system (2026-04-24)

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

## Session 9 — app Flutter v0.1 livrée (2026-04-24)

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

## Session 10 — smoke test sur téléphone + 4 fixes UX (2026-04-25)

Smoke test Step 14.4 du plan v0.1 app déroulé sur Moto g54 5G. Pour contourner un souci réseau Bbox (workstation joint le Pi mais pas le téléphone, malgré même BSSID 5 GHz), montage d'un workaround **tunnel SSH `localhost:8000` → Pi + `adb reverse tcp:8000`** : le téléphone voit le backend comme `localhost:8000`. Pour rendre l'override propre, `PiHost` accepte maintenant `--dart-define=PI_HOST=...` / `--dart-define=PI_PORT=...` (défaut `astro-brain.local:8000`).

Backend live : MOUNT en `error` (ttyUSB0 absent, normal — connecteurs pas encore arrivés), GPS `fix_3d` 16 sats, NETWORK + SYSTEM verts. Tracking observable côté Pi via `journalctl -u astro-brain.service -f` (POST /slew, /stop, /tracking arrivent bien).

**4 remarques relevées au fil → 4 fixes appliqués** :

1. **Splash → Home trop bref / ghost screen** : `SplashCubit` accepte un `minPhaseDuration` (défaut 350 ms). Chaque phase s'affiche au moins ce délai. Total ~1 s minimum au lieu d'un flash.
2. **D-Pad sans feedback au press** : `_Btn` en `StatefulWidget` avec état `_pressed` + `AnimatedContainer` (`motionFast` 120 ms). Au tap-down : `Color.lerp(bg, accent, 0.32)` + bordure `strokeBold` + `BoxShadow(accentGlow, blur 16)`.
3. **Message d'erreur MOUNT trop technique** (`[Errno 2] could not open port…`) : nouvelle util `humanizeMountMessage(String?)` dans `lib/utils/mount_error_messages.dart` qui matche 3 patterns connus + fallback. Appliqué uniquement côté affichage SystemScreen — les logs serveur restent techniques. 6 tests sur le humanizer.
4. **Toggle tracking cliquable malgré mount=error** : `disabled = !connected || mount.state ∉ {ready, moving}`. `buildWhen` reconstruit aussi sur `mount.state`.

**Tests** : 47 → 53 verts (+6 sur le humanizer, +0 régression). `flutter analyze` clean.

**Reste smoke test** : test offline (`adb reverse --remove tcp:8000` + couper le tunnel SSH) → vérifier pastille offline + bouton reconnect. Investiguer isolation client Bbox sélective Pi↔téléphone.
