# v0.2 Setup — Scaffold + Réseau (#8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mettre en place le squelette UI Flutter de la page Setup v0.2 (9 cartes) et l'item #8 Réseau (override host/port persistant côté app), sans toucher au backend ni au hardware. Travail parallèle pendant que la stack INDI compile sur le Pi.

**Architecture:** Refactor de `PiHost` pour lire `SharedPreferences` au runtime (avec fallback `--dart-define` puis défauts mDNS). Extraction d'une AppBar HUD partagée à partir de l'actuel `StatusBar` (paramètre `current` pour désactiver l'icône de l'écran courant + ajout d'une icône engrenage Setup). `SetupScreen` = liste de 9 `SetupCard` (icône + label + sublabel + dot). Seule la carte #8 ouvre un sous-écran fonctionnel en v0.2 (`NetworkScreen` avec `NetworkBloc`) ; les 8 autres cartes sont en placeholder désactivé. Pas de nouveau backend, donc le sous-écran "Tester" tape `GET /state` sur l'adresse saisie.

**Tech Stack:** Flutter, `flutter_bloc` ^9.1.1, `equatable` ^2.0.8, `shared_preferences` ^2.5.5, `phosphor_flutter` ^2.1.0. Tests `flutter_test` + `bloc_test`.

---

## File Structure

**App** :

```
app/lib/
├── services/
│   └── pi_host.dart                     # MODIF : factory async loadFromPrefs(); plus const
├── main.dart                            # MODIF : await PiHost.loadFromPrefs(prefs), passé à app
├── app.dart                             # MODIF : reçoit PiHost en param (plus de const PiHost())
├── widgets/
│   └── astro_app_bar.dart               # NEW : AppBar HUD partagée (status + setup + theme + reconnect)
├── features/
│   ├── home/
│   │   ├── home_screen.dart             # MODIF : remplace StatusBar par AstroAppBar
│   │   └── widgets/status_bar.dart      # SUPPRIMÉ (remplacé par astro_app_bar.dart)
│   ├── system/
│   │   └── system_screen.dart           # MODIF : remplace Material AppBar par AstroAppBar
│   └── setup/
│       ├── setup_screen.dart            # NEW : ListView de 9 SetupCard
│       ├── widgets/
│       │   └── setup_card.dart          # NEW : icône + label + sublabel + dot + tap
│       └── network/
│           ├── network_screen.dart      # NEW : form host/port + Test + Save
│           ├── network_bloc.dart        # NEW
│           ├── network_event.dart       # NEW
│           └── network_state.dart       # NEW
```

**Tests** :

```
app/test/
├── services/
│   └── pi_host_test.dart                # NEW : précédence prefs > define > default
├── widgets/
│   └── astro_app_bar_test.dart          # NEW : icônes présentes, current disable
└── features/setup/
    ├── setup_screen_test.dart           # NEW : 9 cartes, seule #8 cliquable
    └── network/
        ├── network_bloc_test.dart       # NEW : test/save/load happy + error
        └── network_screen_test.dart     # NEW : champs + boutons
```

---

## Task 1: PiHost runtime (factory async + fallback)

**Files:**
- Modify: `app/lib/services/pi_host.dart`
- Test: `app/test/services/pi_host_test.dart`

- [ ] **Step 1: Test précédence prefs > dart-define > defaults**

```dart
// app/test/services/pi_host_test.dart
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('defaults when no prefs and no dart-define', () async {
    final prefs = await SharedPreferences.getInstance();
    final host = PiHost.fromPrefs(prefs);
    expect(host.host, 'astro-brain.local');
    expect(host.port, 8000);
  });

  test('prefs override defaults', () async {
    SharedPreferences.setMockInitialValues({
      'astro.host': '192.168.1.42',
      'astro.port': 9000,
    });
    final prefs = await SharedPreferences.getInstance();
    final host = PiHost.fromPrefs(prefs);
    expect(host.host, '192.168.1.42');
    expect(host.port, 9000);
  });

  test('uri builders honor host/port', () {
    const host = PiHost(host: '10.0.0.1', port: 8080);
    expect(host.restUri('/state').toString(), 'http://10.0.0.1:8080/state');
    expect(host.sseUri('/events').toString(), 'http://10.0.0.1:8080/events');
  });
}
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd app && flutter test test/services/pi_host_test.dart`
Expected: FAIL — `PiHost.fromPrefs` n'existe pas

- [ ] **Step 3: Implement runtime PiHost**

```dart
// app/lib/services/pi_host.dart
import 'package:shared_preferences/shared_preferences.dart';

const _kPrefsHost = 'astro.host';
const _kPrefsPort = 'astro.port';
const _defaultHost = String.fromEnvironment(
  'PI_HOST',
  defaultValue: 'astro-brain.local',
);
const _defaultPort = int.fromEnvironment('PI_PORT', defaultValue: 8000);

/// Résolution de l'hôte du backend Astro-Brain.
///
/// Précédence : `SharedPreferences` (clés `astro.host` / `astro.port`,
/// écrites par l'écran Setup → Réseau) > `--dart-define=PI_HOST/PI_PORT`
/// > défauts mDNS (`astro-brain.local:8000`).
class PiHost {
  const PiHost({this.host = _defaultHost, this.port = _defaultPort});

  factory PiHost.fromPrefs(SharedPreferences prefs) {
    final h = prefs.getString(_kPrefsHost);
    final p = prefs.getInt(_kPrefsPort);
    return PiHost(host: h ?? _defaultHost, port: p ?? _defaultPort);
  }

  final String host;
  final int port;

  Uri restUri(String path) => Uri.http('$host:$port', path);
  Uri sseUri(String path) => Uri.http('$host:$port', path);

  static const String prefsHostKey = _kPrefsHost;
  static const String prefsPortKey = _kPrefsPort;
}
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd app && flutter test test/services/pi_host_test.dart`
Expected: PASS (3/3)

- [ ] **Step 5: Wire dans app.dart et main.dart**

Modifier `app/lib/app.dart` ligne 24 :
```dart
// AVANT : const host = PiHost();
// APRÈS : reçoit en paramètre
class AstroBrainApp extends StatelessWidget {
  const AstroBrainApp({super.key, required this.prefs, required this.host});
  final SharedPreferences prefs;
  final PiHost host;

  @override
  Widget build(BuildContext context) {
    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider<PiHost>.value(value: host),
        // ... reste inchangé
```

Modifier `app/lib/main.dart` :
```dart
import 'services/pi_host.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final host = PiHost.fromPrefs(prefs);
  runApp(AstroBrainApp(prefs: prefs, host: host));
}
```

- [ ] **Step 6: flutter analyze + run tests**

```bash
cd app && flutter analyze && flutter test
```
Expected: PASS (tous les tests existants passent toujours)

- [ ] **Step 7: Commit**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git add app/lib/services/pi_host.dart app/lib/app.dart app/lib/main.dart app/test/services/pi_host_test.dart
git commit -m "feat(app): PiHost runtime via SharedPreferences (prep #8 Réseau)"
```

---

## Task 2: AstroAppBar partagée (HUD)

L'actuel `StatusBar` est une AppBar HUD (HudPanel) utilisée seulement sur Home. La spec exige la même AppBar sur tous les écrans, avec une icône engrenage Setup et un drapeau `current` qui désactive l'icône de l'écran courant.

**Files:**
- Create: `app/lib/widgets/astro_app_bar.dart`
- Modify: `app/lib/features/home/home_screen.dart`
- Modify: `app/lib/features/system/system_screen.dart`
- Delete: `app/lib/features/home/widgets/status_bar.dart` (remplacé)
- Test: `app/test/widgets/astro_app_bar_test.dart`

- [ ] **Step 1: Test du widget AstroAppBar**

```dart
// app/test/widgets/astro_app_bar_test.dart
import 'package:astro_brain/widgets/astro_app_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
// ... imports providers (helpers test à créer si manquants)

void main() {
  testWidgets('shows status, setup gear and theme toggle', (tester) async {
    await tester.pumpWidget(_wrap(const AstroAppBar(current: AstroScreen.home)));
    expect(find.byIcon(PhosphorIconsBold.gearSix), findsOneWidget);
    expect(find.byIcon(PhosphorIconsBold.sun), findsAny); // ou moon selon thème
  });

  testWidgets('disables setup icon when current=setup', (tester) async {
    await tester.pumpWidget(_wrap(const AstroAppBar(current: AstroScreen.setup)));
    final btn = tester.widget<IconButton>(
      find.ancestor(of: find.byIcon(PhosphorIconsBold.gearSix), matching: find.byType(IconButton)),
    );
    expect(btn.onPressed, isNull);
  });
}
```

(Helper `_wrap` fournissant `BlocProvider<AppBloc>`/`ThemeCubit` à définir dans le test.)

- [ ] **Step 2: Run test to verify failure**

Run: `cd app && flutter test test/widgets/astro_app_bar_test.dart`
Expected: FAIL — `AstroAppBar` / `AstroScreen` n'existent pas

- [ ] **Step 3: Implement AstroAppBar**

Copier la structure de `status_bar.dart` actuelle dans `app/lib/widgets/astro_app_bar.dart`, ajouter :

```dart
enum AstroScreen { home, system, setup }

class AstroAppBar extends StatelessWidget {
  const AstroAppBar({super.key, required this.current});
  final AstroScreen current;

  // ...
  // dans le Row, après le Spacer :
  // 1. Reconnect (conditionnel, inchangé)
  // 2. Setup gear : disabled si current == setup, sinon push SetupScreen
  // 3. Theme toggle (inchangé)
  //
  // Le tap sur la pastille overall :
  //   - current == system → no-op (déjà dessus)
  //   - sinon push SystemScreen
}
```

Snippet pour le bouton Setup :
```dart
IconButton(
  tooltip: 'Setup',
  icon: PhosphorIcon(PhosphorIconsBold.gearSix, color: colors.accent),
  onPressed: current == AstroScreen.setup
      ? null
      : () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const SetupScreen()),
          ),
),
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd app && flutter test test/widgets/astro_app_bar_test.dart`
Expected: PASS

- [ ] **Step 5: Migrer Home et System sur AstroAppBar**

`home_screen.dart` : remplacer `StatusBar(...)` par `AstroAppBar(current: AstroScreen.home)`. Supprimer le paramètre `onOpenSystem` du widget — c'est l'AstroAppBar qui pousse `SystemScreen`.

`system_screen.dart` : remplacer le `Scaffold(appBar: AppBar(...))` Material par `Scaffold(body: Column(children: [AstroAppBar(current: AstroScreen.system), Expanded(child: ...)]))`. Le retour arrière : la pastille overall ne fait plus rien sur System (déjà sur System), donc on garde un `BackButton` Material implicit ? Non — on retire le `Scaffold.appBar` Material complètement, et on rajoute juste un caretLeft à gauche de l'AstroAppBar **dans une seconde version (Task suivante)**. Pour cette task, on accepte qu'on revienne via swipe back Android.

Update également `app.dart` `_RootRouter` : `HomeScreen` ne prend plus `onOpenSystem`.

- [ ] **Step 6: Supprimer status_bar.dart**

```bash
git rm app/lib/features/home/widgets/status_bar.dart
```

- [ ] **Step 7: flutter analyze + tests**

```bash
cd app && flutter analyze && flutter test
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(app): AstroAppBar partagée (status + setup + theme + reconnect)"
```

---

## Task 3: SetupCard widget

**Files:**
- Create: `app/lib/features/setup/widgets/setup_card.dart`
- Test: inclus dans `setup_screen_test.dart` (Task 4)

- [ ] **Step 1: Implement SetupCard**

```dart
// app/lib/features/setup/widgets/setup_card.dart
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/overall_status.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

class SetupCard extends StatelessWidget {
  const SetupCard({
    super.key,
    required this.index,
    required this.icon,
    required this.label,
    required this.sublabel,
    required this.dotStatus,
    this.onTap,
  });

  final int index;
  final IconData icon;
  final String label;
  final String sublabel;
  final OverallStatus dotStatus;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final disabled = onTap == null;

    return HudPanel(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        child: Padding(
          padding: const EdgeInsets.all(DesignTokens.spaceLG),
          child: Row(
            children: [
              Text(
                index.toString().padLeft(2, '0'),
                style: text.hudLabel.copyWith(
                  color: disabled ? colors.subtle : colors.accent,
                ),
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              PhosphorIcon(icon, color: disabled ? colors.subtle : colors.accent),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: text.hudLabel.copyWith(
                        color: disabled ? colors.subtle : null,
                      ),
                    ),
                    Text(sublabel, style: text.hudSubtle),
                  ],
                ),
              ),
              GlobalDot(status: dotStatus, size: DesignTokens.statusDotSizeSm),
            ],
          ),
        ),
      ),
    );
  }
}
```

(Si `colors.subtle` ou `text.hudSubtle` n'existent pas tels quels, utiliser les tokens existants équivalents — vérifier `app_colors.dart` / `app_typography.dart` au moment de l'implé. C'est le rôle du subagent.)

- [ ] **Step 2: flutter analyze**

```bash
cd app && flutter analyze app/lib/features/setup/widgets/setup_card.dart
```
Expected: pas d'erreur

- [ ] **Step 3: Commit**

```bash
git add app/lib/features/setup/widgets/setup_card.dart
git commit -m "feat(app): SetupCard widget (icon + label + sublabel + dot)"
```

---

## Task 4: SetupScreen (liste 9 cartes, seul #8 actif)

**Files:**
- Create: `app/lib/features/setup/setup_screen.dart`
- Test: `app/test/features/setup/setup_screen_test.dart`

- [ ] **Step 1: Test SetupScreen affiche 9 cartes, seule #8 cliquable**

```dart
// app/test/features/setup/setup_screen_test.dart
import 'package:astro_brain/features/setup/setup_screen.dart';
import 'package:astro_brain/features/setup/widgets/setup_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
// ... wrappers (cf astro_app_bar_test)

void main() {
  testWidgets('renders 9 cards', (tester) async {
    await tester.pumpWidget(_wrap(const SetupScreen()));
    expect(find.byType(SetupCard), findsNWidgets(9));
  });

  testWidgets('only network card (#8) is enabled in v0.2', (tester) async {
    await tester.pumpWidget(_wrap(const SetupScreen()));
    final cards = tester.widgetList<SetupCard>(find.byType(SetupCard)).toList();
    for (var i = 0; i < cards.length; i++) {
      final isNetwork = (i == 7); // index 0-based -> #8
      expect(cards[i].onTap == null, !isNetwork,
          reason: 'card #${i + 1} onTap mismatch');
    }
  });
}
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd app && flutter test test/features/setup/setup_screen_test.dart`
Expected: FAIL

- [ ] **Step 3: Implement SetupScreen**

```dart
// app/lib/features/setup/setup_screen.dart
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/overall_status.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'network/network_screen.dart';
import 'widgets/setup_card.dart';

class SetupScreen extends StatelessWidget {
  const SetupScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              const AstroAppBar(current: AstroScreen.setup),
              Padding(
                padding: const EdgeInsets.all(DesignTokens.spaceLG),
                child: Text('SETUP', style: text.hudLabel),
              ),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(DesignTokens.spaceLG),
                  children: [
                    SetupCard(
                      index: 1, icon: PhosphorIconsBold.scales,
                      label: 'NIVEAU MONTURE', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 2, icon: PhosphorIconsBold.compass,
                      label: 'COMPASS', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 3, icon: PhosphorIconsBold.arrowsVertical,
                      label: 'ZÉRO ALT', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 4, icon: PhosphorIconsBold.arrowsOutLineVertical,
                      label: 'COURSES ALT', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 5, icon: PhosphorIconsBold.arrowsClockwise,
                      label: 'BACKLASH ALT', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 6, icon: PhosphorIconsBold.arrowsClockwise,
                      label: 'BACKLASH AZ', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 7, icon: PhosphorIconsBold.arrowClockwise,
                      label: 'CORDWRAP AZ', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 8, icon: PhosphorIconsBold.wifiHigh,
                      label: 'RÉSEAU', sublabel: 'Override host/port app',
                      dotStatus: OverallStatus.green,
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const NetworkScreen(),
                        ),
                      ),
                    ),
                    const SizedBox(height: DesignTokens.spaceMD),
                    SetupCard(
                      index: 9, icon: PhosphorIconsBold.info,
                      label: 'À PROPOS', sublabel: 'À implémenter (v0.2)',
                      dotStatus: OverallStatus.gray,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

(Les icônes Phosphor exactes peuvent diverger — l'implémenteur ajuste selon ce qui existe dans `phosphor_flutter` 2.1.0.)

- [ ] **Step 4: Run test to verify pass**

Run: `cd app && flutter test test/features/setup/setup_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/setup/setup_screen.dart app/test/features/setup/setup_screen_test.dart
git commit -m "feat(app): SetupScreen — liste 9 cartes (seule #8 active en v0.2)"
```

---

## Task 5: NetworkBloc

**Files:**
- Create: `app/lib/features/setup/network/network_bloc.dart`
- Create: `app/lib/features/setup/network/network_event.dart`
- Create: `app/lib/features/setup/network/network_state.dart`
- Test: `app/test/features/setup/network/network_bloc_test.dart`

États :
- `NetworkState { String hostInput, int portInput, TestStatus testStatus, String? testError, bool dirty }`
- `TestStatus { idle, testing, ok, error }`
- Saved values = ce qui est dans prefs au load. `dirty = (hostInput, portInput) != saved`.

Events :
- `NetworkLoaded` — émis à l'init, lit `prefs` et populate `hostInput`/`portInput`
- `NetworkHostChanged(String)`, `NetworkPortChanged(int)`
- `NetworkTestRequested` — fait `GET http://hostInput:portInput/state` avec timeout 3 s, met `testStatus`
- `NetworkSaveRequested` — écrit prefs (`astro.host`, `astro.port`)
- `NetworkResetRequested` — efface prefs (revient aux défauts)

- [ ] **Step 1: Test happy path bloc**

```dart
// app/test/features/setup/network/network_bloc_test.dart
import 'package:astro_brain/features/setup/network/network_bloc.dart';
// ...
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  blocTest<NetworkBloc, NetworkState>(
    'load → defaults',
    build: () => NetworkBloc(prefs: _prefs(), httpClient: _fakeOk()),
    act: (b) => b.add(const NetworkLoaded()),
    expect: () => [
      isA<NetworkState>()
          .having((s) => s.hostInput, 'host', 'astro-brain.local')
          .having((s) => s.portInput, 'port', 8000),
    ],
  );

  blocTest<NetworkBloc, NetworkState>(
    'test ok then save persists',
    build: () => NetworkBloc(prefs: _prefs(), httpClient: _fakeOk()),
    act: (b) async {
      b.add(const NetworkLoaded());
      b.add(const NetworkHostChanged('192.168.1.42'));
      b.add(const NetworkPortChanged(9000));
      b.add(const NetworkTestRequested());
      await Future.delayed(const Duration(milliseconds: 50));
      b.add(const NetworkSaveRequested());
    },
    verify: (_) async {
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('astro.host'), '192.168.1.42');
      expect(prefs.getInt('astro.port'), 9000);
    },
  );

  blocTest<NetworkBloc, NetworkState>(
    'test error sets testStatus.error',
    build: () => NetworkBloc(prefs: _prefs(), httpClient: _fakeFail()),
    act: (b) {
      b.add(const NetworkLoaded());
      b.add(const NetworkTestRequested());
    },
    skip: 1,
    expect: () => [
      isA<NetworkState>().having((s) => s.testStatus, 'status', TestStatus.testing),
      isA<NetworkState>().having((s) => s.testStatus, 'status', TestStatus.error),
    ],
  );
}
```

(Helpers `_prefs()`, `_fakeOk()`, `_fakeFail()` au-dessus de `main()`, fournissent `SharedPreferences` et un faux client HTTP.)

- [ ] **Step 2: Run test to verify failure**

Run: `cd app && flutter test test/features/setup/network/network_bloc_test.dart`
Expected: FAIL

- [ ] **Step 3: Implement state/event/bloc**

```dart
// app/lib/features/setup/network/network_state.dart
import 'package:equatable/equatable.dart';

enum TestStatus { idle, testing, ok, error }

class NetworkState extends Equatable {
  const NetworkState({
    required this.hostInput,
    required this.portInput,
    this.testStatus = TestStatus.idle,
    this.testError,
    this.savedHost,
    this.savedPort,
  });

  factory NetworkState.initial() =>
      const NetworkState(hostInput: 'astro-brain.local', portInput: 8000);

  final String hostInput;
  final int portInput;
  final TestStatus testStatus;
  final String? testError;
  final String? savedHost;
  final int? savedPort;

  bool get dirty =>
      savedHost != hostInput || savedPort != portInput;

  NetworkState copyWith({
    String? hostInput,
    int? portInput,
    TestStatus? testStatus,
    String? testError,
    String? savedHost,
    int? savedPort,
  }) =>
      NetworkState(
        hostInput: hostInput ?? this.hostInput,
        portInput: portInput ?? this.portInput,
        testStatus: testStatus ?? this.testStatus,
        testError: testError,
        savedHost: savedHost ?? this.savedHost,
        savedPort: savedPort ?? this.savedPort,
      );

  @override
  List<Object?> get props => [hostInput, portInput, testStatus, testError, savedHost, savedPort];
}
```

```dart
// app/lib/features/setup/network/network_event.dart
import 'package:equatable/equatable.dart';

abstract class NetworkEvent extends Equatable {
  const NetworkEvent();
  @override List<Object?> get props => const [];
}
class NetworkLoaded extends NetworkEvent { const NetworkLoaded(); }
class NetworkHostChanged extends NetworkEvent {
  const NetworkHostChanged(this.host); final String host;
  @override List<Object?> get props => [host];
}
class NetworkPortChanged extends NetworkEvent {
  const NetworkPortChanged(this.port); final int port;
  @override List<Object?> get props => [port];
}
class NetworkTestRequested extends NetworkEvent { const NetworkTestRequested(); }
class NetworkSaveRequested extends NetworkEvent { const NetworkSaveRequested(); }
class NetworkResetRequested extends NetworkEvent { const NetworkResetRequested(); }
```

```dart
// app/lib/features/setup/network/network_bloc.dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../../../services/pi_host.dart';
import 'network_event.dart';
import 'network_state.dart';

class NetworkBloc extends Bloc<NetworkEvent, NetworkState> {
  NetworkBloc({required SharedPreferences prefs, http.Client? httpClient})
      : _prefs = prefs,
        _http = httpClient ?? http.Client(),
        super(NetworkState.initial()) {
    on<NetworkLoaded>(_onLoaded);
    on<NetworkHostChanged>((e, emit) =>
        emit(state.copyWith(hostInput: e.host, testStatus: TestStatus.idle)));
    on<NetworkPortChanged>((e, emit) =>
        emit(state.copyWith(portInput: e.port, testStatus: TestStatus.idle)));
    on<NetworkTestRequested>(_onTest);
    on<NetworkSaveRequested>(_onSave);
    on<NetworkResetRequested>(_onReset);
  }

  final SharedPreferences _prefs;
  final http.Client _http;

  void _onLoaded(NetworkLoaded e, Emitter<NetworkState> emit) {
    final host = _prefs.getString(PiHost.prefsHostKey) ?? 'astro-brain.local';
    final port = _prefs.getInt(PiHost.prefsPortKey) ?? 8000;
    emit(NetworkState(
      hostInput: host, portInput: port, savedHost: host, savedPort: port,
    ));
  }

  Future<void> _onTest(NetworkTestRequested e, Emitter<NetworkState> emit) async {
    emit(state.copyWith(testStatus: TestStatus.testing, testError: null));
    try {
      final uri = Uri.http('${state.hostInput}:${state.portInput}', '/state');
      final r = await _http.get(uri).timeout(const Duration(seconds: 3));
      if (r.statusCode == 200) {
        emit(state.copyWith(testStatus: TestStatus.ok));
      } else {
        emit(state.copyWith(testStatus: TestStatus.error, testError: 'HTTP ${r.statusCode}'));
      }
    } catch (err) {
      emit(state.copyWith(testStatus: TestStatus.error, testError: err.toString()));
    }
  }

  Future<void> _onSave(NetworkSaveRequested e, Emitter<NetworkState> emit) async {
    await _prefs.setString(PiHost.prefsHostKey, state.hostInput);
    await _prefs.setInt(PiHost.prefsPortKey, state.portInput);
    emit(state.copyWith(savedHost: state.hostInput, savedPort: state.portInput));
  }

  Future<void> _onReset(NetworkResetRequested e, Emitter<NetworkState> emit) async {
    await _prefs.remove(PiHost.prefsHostKey);
    await _prefs.remove(PiHost.prefsPortKey);
    emit(NetworkState.initial());
  }

  @override
  Future<void> close() async {
    _http.close();
    return super.close();
  }
}
```

Ajouter `http: ^1.2.0` dans `app/pubspec.yaml` si absent (vérifier d'abord — `flutter` SDK ramène `http` parfois). `bloc_test` aussi en `dev_dependencies`.

- [ ] **Step 4: Run test to verify pass**

Run: `cd app && flutter test test/features/setup/network/network_bloc_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/setup/network/ app/test/features/setup/network/network_bloc_test.dart app/pubspec.yaml app/pubspec.lock
git commit -m "feat(app): NetworkBloc — load/test/save/reset host/port"
```

---

## Task 6: NetworkScreen (UI)

**Files:**
- Create: `app/lib/features/setup/network/network_screen.dart`
- Test: `app/test/features/setup/network/network_screen_test.dart`

UI :
- AstroAppBar(current: setup)
- Titre "RÉSEAU"
- Champs `TextField` host (string) et port (int)
- Pastille "test result" : idle (gray) / testing (blue) / ok (green) / error (red + message)
- Bouton "TESTER" → `NetworkTestRequested`
- Bouton "ENREGISTRER" → `NetworkSaveRequested` + `SnackBar('Redémarrer l\'app pour appliquer')` ; disabled si `!dirty || testStatus != ok`
- Bouton "RÉINITIALISER" → `NetworkResetRequested` + snackbar idem

- [ ] **Step 1: Test affichage + boutons**

```dart
testWidgets('save button disabled until test passes', (tester) async {
  await tester.pumpWidget(_wrap(const NetworkScreen()));
  // Tap TESTER, fake http renvoie ok, save devient enabled
});
```

- [ ] **Step 2: Run test to verify failure**

- [ ] **Step 3: Implement NetworkScreen**

(Pattern Form classique, BlocBuilder + BlocListener pour les snackbars.)

- [ ] **Step 4: Run test to verify pass**

- [ ] **Step 5: flutter analyze**

```bash
cd app && flutter analyze
```

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/setup/network/network_screen.dart app/test/features/setup/network/network_screen_test.dart
git commit -m "feat(app): NetworkScreen — formulaire host/port + Tester/Enregistrer"
```

---

## Task 7: Smoke test sur Android physique

**Files:**
- Modify: `docs/project/journal.md` (entrée session)

CLAUDE.md exige validation visuelle sur Android USB (pas Chrome / pas émulateur). Ce test est **manuel**, fait par l'utilisateur ; le subagent prépare la build et donne les pas.

- [ ] **Step 1: Build Android et installer sur device**

```bash
cd app && flutter run -d <device-id>
```

- [ ] **Step 2: Checklist visuelle**

- [ ] L'AstroAppBar apparaît identique sur Home, System, Setup
- [ ] L'icône engrenage Setup ouvre la page Setup ; sur Setup elle est désactivée
- [ ] La page Setup affiche 9 cartes ; seule #8 RÉSEAU réagit au tap
- [ ] La page Réseau permet de changer host/port, "Tester" ping le backend, "Enregistrer" persist
- [ ] Après redémarrage de l'app, la nouvelle adresse est utilisée (l'app se connecte si elle est correcte)
- [ ] "Réinitialiser" remet `astro-brain.local:8000`

- [ ] **Step 3: Si OK, mettre à jour journal.md**

Ajouter une session "v0.2 Setup — scaffold + #8 Réseau" décrivant : pivot scope v0.2, AstroAppBar partagée, SetupScreen squelette, item Réseau opérationnel, parallèle au build libindi côté Pi.

- [ ] **Step 4: Commit journal**

```bash
git add docs/project/journal.md
git commit -m "docs(journal): v0.2 — scaffold Setup + Réseau (#8) livrés"
```

---

## Task 8: Merge feat/v02-setup-scaffold → main

**Files:** —

- [ ] **Step 1: Vérifier que tout passe**

```bash
cd app && flutter analyze && flutter test
```
Expected: PASS partout.

- [ ] **Step 2: Merge**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git checkout main
git merge --no-ff feat/v02-setup-scaffold
```

(Confirmer avec l'utilisateur avant `merge --no-ff` si auto mode désactivé.)

- [ ] **Step 3: Cleanup branche locale**

```bash
git branch -d feat/v02-setup-scaffold
```

---

## Notes pour l'implémenteur

- **Branche déjà créée** : `feat/v02-setup-scaffold`. Vérifier `git branch --show-current` avant de commencer.
- **Backend INDI** : ne PAS toucher au backend dans ce plan. La tâche backend Setup (sensors, calibration, etc.) viendra dans un plan séparé après livraison du sous-projet INDI mount.
- **Le widget StatusBar v0.1 est supprimé**, intégralement remplacé par `AstroAppBar`. Préserver son comportement exact (HudPanel, pastille tap → System, reconnect conditionnel, theme toggle).
- **Le 9ème écran (À propos)** n'est pas implémenté ici — sa carte Setup reste désactivée. Idem pour les 7 cartes hardware/AUX. Elles deviendront actives au fil des prochains plans v0.2.
- **Pas de schéma DB** modifié, pas d'API backend ajoutée. Tout le travail est côté `app/`.
