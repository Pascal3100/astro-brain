# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. Seule la **session en cours** vit ici en détail ; les sessions passées sont archivées par milestone dans `docs/journal/archive/`.

## État du projet

**Version active** : `v0.1 app Flutter livrée` — parité joystick + tracking avec la raquette Celestron via téléphone. 3 écrans (Splash, Home, System), 47/47 tests Dart verts, mDNS `astro-brain.local:8000`. Backend `v0.1 backend` toujours en place côté Pi (64 tests verts, service systemd actif). Validation physique backend faite sur **GPS + compass I2C + network + system** ; **monture pas encore branchée** (sections 3 et 7 de `backend/deploy/INTEGRATION_CHECKLIST.md` à dérouler).

**Prochain jalon** : smoke test téléphone sur `flutter run` (checklist Step 14.4 du plan app) + passe avec monture Celestron branchée pour clore définitivement la v0.1 backend. Ensuite, ouverture v0.2 (GoTo + alignement 3 étoiles).

## Session en cours

### Session 6 — revue de code v0.1 + renforcement (2026-04-20 / 21)

Grosse revue de code sur tout le backend produit (Tasks 1→17 du plan v0.1). Verdict du reviewer : **« ship with caveats »** — 5 Critical + 6 Significant + nits. Consigne utilisateur : traiter Critical + Significant sans créer de document dédié, uniquement en commits.

Traité en 4 batches :

- **Batch 1 — purification de l'aggregator + chemins env-driven** (commit `ship-with-caveats` series)
    - `aggregator.py` : `FATAL_STATES` / `TRANSIENT_STATES` / `DEGRADED_STATES` dérivés des enums `MountState` / `GpsState` / `NetworkState` / `SystemInfoState`. Un rename dans `subsystems.py` casse maintenant l'aggregator à l'import au lieu de classer silencieusement mal.
    - `"gps=off"` ajouté dans `DEGRADED_STATES` (avant il était traité comme `green`).
    - Variables d'environnement introduites : `ASTRO_BRAIN_SERIAL_DEVICE` (nexstar), `ASTRO_BRAIN_WIFI_IFACE` (network_info). Plus besoin de patcher le code pour tester sur un laptop.

- **Batch 2 — logging + frontières d'exceptions**
    - `orchestrator.py` : `logger.info(...)` au moment du sync et du désarmement — traçable via `journalctl`.
    - `gpsd_adapter.py` : `logger.warning("gpsd poll failed", exc_info=True)` au lieu d'un `except Exception: continue` muet.
    - `nexstar_adapter.py` : `set_time` / `set_location` enveloppés dans try/except qui publient `mount=error` au lieu de faire péter tout le boot.
    - Message du watchdog mount précis (« Restart astro-brain.service to reconnect »), référence à la section 3 de `INTEGRATION_CHECKLIST.md`.

- **Batch 3 — `asyncio.to_thread` pour l'I/O hardware bloquant**
    - `nexstarpy` (constructor, `get_version`, `slew_fixed`, `stop_slew`, `set_time`, `set_location`, `set_tracking_mode`, `close`) : chaque appel synchrone série (9600 baud, 10-50 ms) tourne maintenant sur le thread-pool par défaut. La boucle asyncio reste réactive aux clients SSE, aux handlers REST, et au watchdog.
    - `gpsd-py3` : `gpsd.connect()` et `gpsd.get_current()` offloadés.
    - `network_info.py` : `_compute_network` (subprocess `ip` + `iwgetid`) offloadé ; `_publish_current` devenu async en conséquence.
    - `bus.py` : le docstring documente maintenant explicitement l'invariant « `publish()` ne se fait que sur la main-loop asyncio ». Les adapters qui reviennent du thread-pool via `await asyncio.to_thread(...)` reprennent sur la main-loop avant de publier — invariant préservé.

- **Batch 4 — `deps.py` : fin de la mutation de module**
    - Le pattern `deps.get_bus = lambda: bus` a été remplacé par un pattern FastAPI idiomatique : chaque resolver prend un `Request` et lit `request.app.state.<service>`. Les routes déclarent leurs collaborateurs via `Depends(deps.get_<name>)`.
    - `build_app` installe le bus + les 5 services sur `app.state` au lieu de muter le module `deps`. Chaque instance de FastAPI est désormais autonome : deux apps peuvent co-exister (app réelle + app de test) sans se piétiner.
    - Fixtures de tests : plus de `prev = deps.get_bus ; deps.get_bus = lambda: bus ; ... ; deps.get_bus = prev`. À la place, les tests instancient leur propre `FastAPI()`, peuplent `app.state`, et exposent un `Harness(client, bus)` pour taper directement sur le bus dans les assertions.
    - Test du SSE `/events` : comme il bypasse la couche HTTP et invoque `events(...)` directement, on passe maintenant `bus=` explicitement (le `Depends(...)` n'est résolu que dans le flot HTTP de FastAPI).

64/64 tests verts à chaque batch. Les nits de la revue (typos, docstrings minimaux) ne sont pas traités pour l'instant — ils peuvent attendre le premier vrai cycle de maintenance.

**À faire ensuite** :
- Session de validation physique (câblage GPS, checklist hardware) pour clore officiellement le milestone « v0.1 backend ».
- Ce journal sera archivé au moment du démarrage du plan v0.1 app Flutter.

### Session 6 (suite) — validation physique GPS + compass + 2 fixes (2026-04-21)

GPS DroTek M8N branché sur UART GPIO + compass I2C. Passe de validation partielle (monture pas encore branchée) : sections 0, 1, 2, 4, 5, 6 de `backend/deploy/INTEGRATION_CHECKLIST.md` cochées, findings documentés.

**Section 0 étoffée** — trois étapes qui manquaient à la checklist initiale ont été ajoutées après découverte sur le terrain :
- Charger `i2c-dev` + persistance via `/etc/modules-load.d/i2c-dev.conf` (sans ça, `dtparam=i2c_arm=on` active le bus mais `/dev/i2c-1` n'apparaît pas).
- Désactiver `serial-getty@ttyAMA0.service` (la console de login squatte le port série et bloque gpsd avec `SER: already opened by another process`).
- Retirer `console=serial0,115200` de `/boot/firmware/cmdline.txt` (le kernel y pousse ses logs et pollue les trames NMEA).
- Note : `hciuart.service` n'existe plus sur Pi OS 64-bit Lite récent, `dtoverlay=disable-bt` suffit.

**Résultats hardware** :
- GPS u-blox NEO-M8N, fix_3d atteint en ~30 s (43.5023 N, 1.5194 E à Toulouse), 14 satellites utilisés, HDOP 0.83, 4 constellations (GPS/GLONASS/Galileo/BeiDou).
- Compass I2C : **LIS3MDL** (ST Microelectronics) à `0x1E`, identifié via `WHO_AM_I=0x3D`. Pas un HMC5883L contrairement à ce que supposait `docs/hardware_wiring.md` avant cette passe. Activé en mode continu (`CTRL_REG1=0x1C`, `CTRL_REG3=0x00`, `CTRL_REG4=0x0C`), mesures 3 axes live confirmées (variations de magnitude/heading quand on tourne le module). Non utilisé par la v0.1 backend, prêt pour v0.2.
- Network en mode `client`, SSID + IP corrects.
- System idle à 56 °C, load 0.05.

**Deux bugs découverts et fixés** (commit `57e7553`) :
- `gpsd_adapter` : `gpsd-py3.get_current()` renvoie le **dernier paquet** (typiquement TPV sans champ `sats`), pas un état agrégé. Résultat : `details.satellites = 0` alors que le GPS voit 14 sats. Fix : cacher la dernière valeur `sats_valid > 0` lue dans une trame SKY et l'utiliser comme valeur courante.
- `nexstar_adapter` : le subsystem `tracking` n'était publié **qu'après** une init monture réussie — quand la monture est débranchée (mount=error), `/state` ne remontait que 4 subsystems au lieu des 5 attendus par la checklist. Fix : publier `tracking=off` dès l'entrée de `start()`, avant la tentative de connexion.

64/64 tests verts après fix. Validation live post-deploy : `/state` remonte bien `tracking: off` + `satellites: 14`, les 5 subsystems présents.

**À faire** : passe dédiée avec monture Celestron branchée pour clore la v0.1 backend (sections 3 et 7 de la checklist).

### Session 7 — décision capteurs d'inclinaison (2026-04-24)

Arbitrage hardware sur la mesure d'inclinaison : choix de **2 × ADXL345** (accéléromètres I2C simples) plutôt qu'un IMU 9DOF.

- **ADXL345 tube** (`0x53`) → zéro ALT + détection butées d'inclinaison
- **ADXL345 monture** (`0x1D`) → mise à niveau pré-session (bulle virtuelle)

Justification : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas besoin de fusion de capteurs ni de cap tilt-compensé (le plate solve v0.4 prendra le relais pour le pointage précis). Les 2 modules cohabitent sur I2C1 grâce à la pin SDO qui sélectionne l'adresse — pas de multiplexeur, pas de conflit avec le LIS3MDL (`0x1E`).

Capteurs commandés. Détails et pages UI associées dans `docs/backlog.md` (section "Capteurs d'inclinaison tube + monture"). Mentions liées mises à jour : v0.2 mise en station (niveau), v0.5 réglages techniques monture (courses ALT), et piste IMU de "Position persistante" (écartée).

### Session 8 — démarrage app Flutter v0.1, thème + design system (2026-04-24)

Attente des connecteurs monture → on ouvre le chantier app Flutter en parallèle. Choix d'archi : **pattern BLoC** (MVVM-like) via `flutter_bloc`, bible officielle `docs.flutter.dev`. Noté en mémoire persistante.

Scaffold Flutter dans `app/` (`flutter create --org com.astrobrain --project-name astro_brain`, platforms `android,ios,linux`). Stack Flutter 3.41.6 / Dart 3.11.4. Dépendances ajoutées : `flutter_bloc`, `equatable`, `google_fonts` (Inter + JetBrains Mono), `phosphor_flutter`.

**Design system posé en 5 fichiers sous `lib/theme/`** — l'objectif est de ne *plus* répéter couleurs/espaces/styles dans les pages à venir :

- `design_tokens.dart` — constantes brutes extraites de la spec (couleurs jour/nuit, échelle d'espacement base 4, rayons, épaisseurs, durations, tailles d'icônes).
- `app_colors.dart` — `AppColors` en `ThemeExtension<AppColors>` : slots sémantiques que M3 n'a pas (`accent`, `accentGlow`, `bgGradientTop/Bottom`, `grid`, `textPrimary/Muted`, `dotOk/Transition/Warn/Error`). Deux instances `const` : `AppColors.day` (bleu spatial) et `AppColors.night` (rouge astro, aucun bleu ni vert). Extension `context.colors` pour l'accès.
- `app_typography.dart` — `buildInterTextTheme(color:)` pour le `TextTheme` M3 en Inter ; `AppTextStyles` en `ThemeExtension` pour les styles HUD monospace JetBrains Mono (`hudLabel`, `hudValue`, `hudCaption`, `hudBadge`). Extension `context.textStyles`.
- `astro_theme.dart` — `AstroTheme.buildDay()` / `buildNight()` : `ThemeData` M3, `Brightness.dark` pour les deux (les deux thèmes sont sur fond sombre, le toggle ne change que la teinte d'accent), `ColorScheme` mappé à la main sur nos tokens, themes pour `FilledButton`, `OutlinedButton`, `TextButton`, `Card`, `AppBar`, `Divider`, `IconTheme`. `ThemeExtensions` injectées via `extensions:`.
- `theme_cubit.dart` — `ThemeCubit extends Cubit<AstroThemeMode>` avec `toggle()`, `setDay()`, `setNight()`. Défaut = jour. Persistance `shared_preferences` à ajouter plus tard.

**`main.dart`** : `AstroBrainApp` (StatelessWidget racine) expose `BlocProvider<ThemeCubit>` et un `BlocBuilder` qui choisit `ThemeMode.light`/`dark` → `MaterialApp.theme`/`darkTheme`. Une page provisoire `_ThemePreviewScreen` valide visuellement tous les tokens (dots d'état, typographie Inter + JBM, boutons, card HUD avec icône Phosphor `gpsFix` + pastille glow). Elle sera remplacée par la vraie `SplashScreen` au prochain plan.

**Vérifications** :
- `flutter analyze` → No issues found.
- `flutter test` → 5/5 passent (AppColors × 2, ThemeCubit × 3). Les tests qui instancient directement `AstroTheme.buildDay()` sont volontairement absents : `google_fonts` tente un fetch HTTP au `GoogleFonts.jetBrainsMono()`, ce qui génère une erreur async non rattrapée en sandbox sans réseau. La validation visuelle se fait à `flutter run` ; on réactivera ces tests quand on bundlera les TTF en assets locaux.

**Pattern d'accès aux tokens** (à utiliser dans les prochaines pages) :
```dart
final colors = context.colors;        // AppColors (ThemeExtension)
final text = context.textStyles;      // AppTextStyles (ThemeExtension)
DesignTokens.spaceLG;                 // constante brute
```
Aucun `Color(0xFF...)` ne devrait apparaître hors de `design_tokens.dart`. Aucun `GoogleFonts.inter(...)` hors de `app_typography.dart`.

**À faire ensuite** :
- Spec de détail Flutter v0.1 (plan d'implémentation des 3 écrans : `SplashScreen`, `HomeScreen`, `SystemScreen`). Le design est déjà défini dans la spec v0.1 (docs/superpowers/specs/…), il manque le plan tâches.
- Modèles Pydantic ↔ Dart (`SubsystemState`, `SystemState`) + services `ApiService` / `EventStreamService` / `ConnectivityService` en parallèle.
- Ajouter `shared_preferences` pour persister `AstroThemeMode` entre lancements.
- Reprendre la validation monture dès que les connecteurs arrivent (sections 3 et 7 de `INTEGRATION_CHECKLIST.md`).

### Session 9 — app Flutter v0.1 livrée (2026-04-24)

Exécution du plan `docs/superpowers/plans/2026-04-24-astro-brain-v01-app.md` en mode **subagent-driven**, 17 tâches enchaînées. Résultat : 3 écrans fonctionnels, toute la mécanique REST + SSE + état global en place.

**Écrans livrés** :
- `SplashScreen` — 3 phases séquentielles (`contacting` → `loading` → `openingStream`), fallback `failure` avec bouton "continue offline" et icône Phosphor `planet` (pas de `telescope` en phosphor_flutter 2.1.0).
- `HomeScreen` — gradient bg, `StatusBar` en haut (pastille globale + toggle thème + bouton reconnect conditionnel), `DPadControl` 3×3 central (caret icons, `onTapDown/Up/Cancel` → slew / stop), `RateControl` (9 barres + / - 1..9, clamp côté bloc), `TrackingToggle` (Switch + libellé `TRACKING SIDEREAL` / `TRACKING OFF`, grisé si `connection != connected`).
- `SystemScreen` — 5 `SubsystemCard` (MOUNT / GPS / TRACKING / NETWORK / SYSTEM), chacune avec icône, libellé, détails contextuels (`firmware`, coordonnées GPS + sats, ssid + ip, temp + load), `depuis Xs/Xmin/Xh`, pastille `GlobalDot` calculée par subsystem, message d'erreur optionnel en rouge.

**Blocs / Cubits** :
- `AppBloc` — état global `(system: SystemState?, connection: ConnectionStatus)`, événements `AppStarted` / `AppSystemStateReceived` / `AppConnectionLost` / `AppReconnectRequested`. Expose `effectiveOverall` (calcul d'une pastille globale à partir des 5 sous-systèmes + statut connexion).
- `HomeBloc` — `rate` 1..9 (défaut 5, clamp), event `HomeSlewPressed/Released` → `ApiService.slew/stop`, `HomeTrackingToggled` → `ApiService.setTracking`. try/catch autour de chaque appel, erreur exposée via `lastError`.
- `SplashCubit` — orchestre la séquence de boot : `fetchState` → `appBloc.add(AppStarted)` → `success`. En cas d'exception, émet `failure` avec message ; l'utilisateur peut `continueOffline()`.
- `ThemeCubit` — `AstroThemeMode { day, night }`, persistance `shared_preferences` (clé `astro.theme.mode`). Hydrate au démarrage via `await SharedPreferences.getInstance()` en tête de `main()`.

**Services** :
- `ApiService` — REST sur `astro-brain.local:8000`, timeout 3 s, `fetchState()` / `slew()` / `stop()` / `setTracking()`. Convertit les erreurs HTTP en `ApiException`.
- `EventStreamService` — client SSE par-dessus `http.Client.send()`, broadcast `Stream<SystemState>`, reconnexion auto avec backoff exp `[1s, 2s, 4s, 10s]`. Distinction `stop()` (coupe la connexion, réutilisable) vs `dispose()` (ferme le controller — fin de vie). Le bouton reconnect manuel (Task 16) a forcé ce split.
- `SseParser` — parse incrémental des chunks, supporte `event:` / `data:` / commentaires `:` / multi-lignes concaténées / split mid-ligne entre deux chunks.

**Modèles** :
- `SubsystemState<T>` générique (`state: T`, `since: DateTime`, `message: String?`, `details: Map<String, dynamic>`).
- `SystemState` (5 subsystems typés) avec `fromJson` (snapshot) et `applyUpdate` (patch incrémental SSE, branche mount/gps/tracking/network/system, throw sur subsystem inconnu).
- `OverallStatus { green, blue, orange, red, offline }` + 5 enums sous-systèmes (parse tolérant aux minuscules, throw sur valeur inconnue).

**Racine app** : `lib/app.dart` — `AstroBrainApp({required SharedPreferences prefs})` avec `MultiRepositoryProvider` (PiHost → ApiService → EventStreamService), `MultiBlocProvider` (ThemeCubit, AppBloc, HomeBloc), `MaterialApp` pilotée par `ThemeCubit` (light↔day / dark↔night), `_RootRouter` qui flip un `_ready` bool quand le splash finit (via `onReady` callback déclenché dans le `BlocListener` du splash sur `SplashPhase.success`).

**Tests** : 47/47 verts. Coverage majeur sur modèles (parse + applyUpdate), `SseParser` (5 cas), `ApiService` (5 cas avec `http.MockClient`), `EventStreamService` (2 cas avec fake client), `AppBloc` (2 blocTest), `HomeBloc` (3 blocTest avec `registerFallbackValue` pour `Axis` / `Direction`), `SplashCubit` (2 blocTest), `ThemeCubit` (3 cas, `SharedPreferences.setMockInitialValues({})` + async).

**Hors scope v0.1, laissé pour plus tard** : configuration manuelle d'IP/port (écran de setup), mode hotspot côté Pi pour usage terrain sans Wi-Fi domestique, mDNS fallback sur IP en dur en cas d'échec résolution, smoke test téléphone (Step 14.4 du plan — validation manuelle sur Android physique à faire).

**Contraintes rencontrées** :
- Collision de nom `Axis` (Flutter `dart:ui` vs notre enum dans `api_service.dart`) — résolu par `import 'package:flutter/material.dart' hide Axis;` dans `dpad_control.dart`.
- `PhosphorIconsBold.telescope` n'existe pas en 2.1.0 — substitué par `planet` sur le splash.
- `google_fonts` fait un fetch HTTP au premier usage ; les tests qui instancient `AstroTheme.buildDay()` ne sont toujours pas dans la suite (déjà noté Session 8). Les validations visuelles passent par `flutter run`.

**Commits** : 17 commits entre `16d38eb` (baseline scaffold + session 8) et `fceec5e` (Task 16 reconnect manuel).

**À faire ensuite** :
- Smoke test manuel sur téléphone Android (Step 14.4 du plan : splash → home → system → D-Pad → tracking → toggle thème → débranchement réseau → bouton reconnect).
- Passe monture Celestron pour fermer la v0.1 backend (sections 3 et 7 de `INTEGRATION_CHECKLIST.md`).
- Démarrage v0.2 : GoTo + alignement 3 étoiles (exploite GPS + compass LIS3MDL + ADXL345 tube).

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→5 (brainstorm, spec design, monorepo + uv, Tasks 1-16 du plan backend, checklist hardware).
