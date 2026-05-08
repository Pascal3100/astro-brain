# Hub central — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer le Hub central comme nouvelle landing post-Splash, avec 4 cartes (MANUEL · SETUP · STATUS · À PROPOS) en liste verticale, et promouvoir HomeScreen→ManualScreen et AboutScreen hors de Setup.

**Architecture:** `HubScreen` est un `StatelessWidget` sans BLoC qui rend une `ListView` de `HubCard`. Le routing root (`app.dart::_RootRouter`) atterrit sur Hub au lieu de Home. L'enum `AstroScreen` gagne `hub` et `manual`, perd `home`. Les écrans cibles (Manual, Setup, System, About) restent fonctionnellement identiques, seules leurs identités d'enum changent là où nécessaire.

**Tech Stack:** Flutter 3.11+, Material 3, `flutter_bloc` (inchangé), `phosphor_flutter` 2.1 (UI utility icons + chevron), `hugeicons` 1.1.6 (hero icons des cartes), `flutter_test`/`mocktail`/`bloc_test` pour les tests widgets et BLoC.

---

## Spec

[`docs/superpowers/specs/2026-05-08-hub-central-design.md`](../specs/2026-05-08-hub-central-design.md)

## File Structure

**Créer :**
- `app/lib/features/hub/hub_screen.dart` — l'écran Hub (Stateless, ListView de 4 HubCard).
- `app/lib/features/hub/widgets/hub_card.dart` — widget réutilisable pour une carte.
- `app/test/features/hub/hub_screen_test.dart` — tests widgets de HubScreen.
- `app/test/features/hub/widgets/hub_card_test.dart` — tests widgets de HubCard.

**Renommer/déplacer :**
- `app/lib/features/home/` → `app/lib/features/manual/` (HomeScreen→ManualScreen, HomeBloc→ManualBloc, etc.)
- `app/lib/features/setup/about/` → `app/lib/features/about/`
- `app/test/features/home/` → `app/test/features/manual/`
- `app/test/features/setup/about/` → `app/test/features/about/`

**Modifier :**
- `app/lib/widgets/astro_app_bar.dart` — enum `AstroScreen` : ajouter `hub`, renommer `home`→`manual`.
- `app/lib/app.dart` — imports + `_RootRouter.build` pour retourner `HubScreen`, BlocProvider `ManualBloc`.
- `app/lib/features/setup/setup_screen.dart` — supprimer la carte #9 About, passer `itemCount` de 9 à 8, retirer la case 9 du switch et la méthode `_buildAboutCard` + `_openAbout` + `_aboutRefresh`.
- `app/lib/features/manual/manual_screen.dart` — `current: AstroScreen.manual` (ex `home`).
- `app/test/widgets/astro_app_bar_test.dart` — remplacer `AstroScreen.home` par `AstroScreen.manual` dans les tests existants.
- `docs/project/roadmap.md` — marquer Macro 3 item #1 livré.
- `docs/product/features/hub.md` — créer la fiche feature.
- `docs/project/journal.md` — entrée Session 20.

---

## Branch

Crée une branche dédiée avant de commencer :

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git checkout -b feat/macro3-hub-central
```

Tous les commits du plan vont sur cette branche. PR fusionnée à la fin.

---

## Task 1 — Étendre l'enum `AstroScreen` (hub + manual)

**Files:**
- Modify: `app/lib/widgets/astro_app_bar.dart:15`

**Pourquoi en premier :** les renames qui suivent (Home→Manual) compilent plus simplement si l'enum cible existe déjà.

- [ ] **Step 1: Ajouter les valeurs `hub` et `manual` à l'enum sans retirer `home` encore**

Édite `app/lib/widgets/astro_app_bar.dart:15` :

```dart
enum AstroScreen { hub, manual, home, system, setup }
```

`home` reste temporairement pour ne pas casser `home_screen.dart` avant le rename.

- [ ] **Step 2: `flutter analyze` doit passer**

```bash
cd app && flutter analyze
```
Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add app/lib/widgets/astro_app_bar.dart
git commit -m "refactor(app): add AstroScreen.hub and .manual (transitional, home kept)"
```

---

## Task 2 — Rename `features/home/` → `features/manual/` (lib + test)

**Files:**
- Move: `app/lib/features/home/` → `app/lib/features/manual/` (4 fichiers + dossier `widgets/`)
- Move: `app/test/features/home/` → `app/test/features/manual/`
- Modify: `app/lib/features/manual/manual_screen.dart` (ex home_screen.dart) — class rename + AstroScreen.manual
- Modify: `app/lib/features/manual/manual_bloc.dart`, `manual_event.dart`, `manual_state.dart` — class renames
- Modify: `app/lib/features/manual/widgets/dpad_control.dart`, `rate_control.dart`, `tracking_toggle.dart` — references à HomeBloc/HomeEvent
- Modify: `app/lib/app.dart:5-6,46-47,88` — imports + BlocProvider + `_RootRouter` cible (laisse Hub pour Task 6, ici on cible `ManualScreen` temporairement)
- Modify: `app/test/features/manual/manual_bloc_test.dart` — imports + class names

- [ ] **Step 1: Déplacer les fichiers via git pour préserver l'historique**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git mv app/lib/features/home app/lib/features/manual
git mv app/lib/features/manual/home_bloc.dart app/lib/features/manual/manual_bloc.dart
git mv app/lib/features/manual/home_event.dart app/lib/features/manual/manual_event.dart
git mv app/lib/features/manual/home_state.dart app/lib/features/manual/manual_state.dart
git mv app/lib/features/manual/home_screen.dart app/lib/features/manual/manual_screen.dart
git mv app/test/features/home app/test/features/manual
git mv app/test/features/manual/home_bloc_test.dart app/test/features/manual/manual_bloc_test.dart
```

- [ ] **Step 2: Renommer les classes et events à l'intérieur des fichiers**

Mappage exhaustif (chaque occurrence à remplacer dans les fichiers déplacés ET dans `app.dart`, `astro_app_bar.dart` n'a pas de référence Home*) :

| Avant | Après |
|---|---|
| `HomeScreen` | `ManualScreen` |
| `HomeBloc` | `ManualBloc` |
| `HomeState` | `ManualState` |
| `HomeEvent` | `ManualEvent` |
| `HomeRateChanged` | `ManualRateChanged` |
| `HomeSlewPressed` | `ManualSlewPressed` |
| `HomeSlewReleased` | `ManualSlewReleased` |
| `HomeTrackingToggled` | `ManualTrackingToggled` |
| `import 'home_bloc.dart'` etc. | `import 'manual_bloc.dart'` etc. |
| `features/home/` (dans imports) | `features/manual/` |
| `AstroScreen.home` (dans `manual_screen.dart`) | `AstroScreen.manual` |

Fichiers à éditer :
- `app/lib/features/manual/manual_screen.dart` : class + AppBar `current: AstroScreen.manual`
- `app/lib/features/manual/manual_bloc.dart` : class + types
- `app/lib/features/manual/manual_event.dart` : classes events
- `app/lib/features/manual/manual_state.dart` : class
- `app/lib/features/manual/widgets/dpad_control.dart` : `read<HomeBloc>` → `read<ManualBloc>`, `add(HomeSlewPressed/Released(...))` → `add(ManualSlewPressed/Released(...))`
- `app/lib/features/manual/widgets/rate_control.dart` : `BlocBuilder<HomeBloc, HomeState>` → `BlocBuilder<ManualBloc, ManualState>`, `add(HomeRateChanged(...))` → `add(ManualRateChanged(...))`
- `app/lib/features/manual/widgets/tracking_toggle.dart` : idem `HomeTrackingToggled` → `ManualTrackingToggled` et `HomeBloc`
- `app/lib/app.dart` : `import 'features/home/home_bloc.dart'` → `'features/manual/manual_bloc.dart'`, idem screen, `BlocProvider<HomeBloc>` → `BlocProvider<ManualBloc>`, `HomeBloc(api: ...)` → `ManualBloc(api: ...)`, `_RootRouterState.build` retourne `const ManualScreen()` (le Hub viendra Task 6).
- `app/test/features/manual/manual_bloc_test.dart` : imports + class names

- [ ] **Step 3: `flutter analyze` doit passer**

```bash
cd app && flutter analyze
```
Expected: `No issues found!` Si l'analyzer flag des `Home*` qui restent, corrige et relance.

- [ ] **Step 4: Tests existants passent**

```bash
cd app && flutter test test/features/manual/
```
Expected: tous verts.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(app): rename HomeScreen → ManualScreen (feature manual/)

Spec Hub central : HomeScreen (joystick) devient ManualScreen, feature
parmi les autres. Pas de changement de comportement, renommage pur
classes + folder + tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3 — Retirer `home` de l'enum `AstroScreen`

**Files:**
- Modify: `app/lib/widgets/astro_app_bar.dart:15`
- Modify: `app/test/widgets/astro_app_bar_test.dart:84,110` — remplacer `AstroScreen.home` → `AstroScreen.manual`

- [ ] **Step 1: Mettre à jour l'enum**

Édite `app/lib/widgets/astro_app_bar.dart:15` :

```dart
enum AstroScreen { hub, manual, system, setup }
```

- [ ] **Step 2: Mettre à jour les tests AppBar**

Dans `app/test/widgets/astro_app_bar_test.dart` :
- Ligne 84 : `testWidgets('renders gear icon and theme toggle on home', ...)` → `'renders gear icon and theme toggle on manual'`
- Ligne 86 : `AstroScreen.home` → `AstroScreen.manual`

- [ ] **Step 3: `flutter analyze` + tests AppBar passent**

```bash
cd app && flutter analyze && flutter test test/widgets/astro_app_bar_test.dart
```
Expected: clean + tests verts.

- [ ] **Step 4: Commit**

```bash
git add app/lib/widgets/astro_app_bar.dart app/test/widgets/astro_app_bar_test.dart
git commit -m "refactor(app): drop AstroScreen.home, finalize manual rename"
```

---

## Task 4 — Sortir About de Setup (move folder)

**Files:**
- Move: `app/lib/features/setup/about/` → `app/lib/features/about/`
- Move: `app/test/features/setup/about/` → `app/test/features/about/`
- Modify: `app/lib/features/setup/setup_screen.dart:14,90-95,193-212,243` — retirer import About, méthode `_openAbout`, `_buildAboutCard`, `_aboutRefresh`, et la case 9 du switch + passer `itemCount` à 8
- Modify: `app/lib/features/about/about_screen.dart:50` — changer `current: AstroScreen.setup` → `current: AstroScreen.about` (cf Task 5 pour ajouter `about` à l'enum)

> ⚠️ Cette task ajoute aussi `about` à l'enum (Task 5 originalement séparée — fusionnée ici car indissociable du déplacement). Voir Step 1 ci-dessous.

- [ ] **Step 1: Étendre l'enum avec `about`**

Édite `app/lib/widgets/astro_app_bar.dart:15` :

```dart
enum AstroScreen { hub, manual, system, setup, about }
```

- [ ] **Step 2: Déplacer les fichiers**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git mv app/lib/features/setup/about app/lib/features/about
git mv app/test/features/setup/about app/test/features/about
```

- [ ] **Step 3: Mettre à jour `about_screen.dart`**

Dans `app/lib/features/about/about_screen.dart`, ligne 50 :

```dart
const AstroAppBar(current: AstroScreen.about),
```

Et vérifier que les imports relatifs (vers `models/`, `services/`, etc.) restent corrects après le déplacement — le fichier monte d'un niveau, donc `../../models/` reste valide (3 niveaux up depuis `features/about/`). Lance `flutter analyze` après les renames pour vérifier.

- [ ] **Step 4: Retirer About de SetupScreen**

Édite `app/lib/features/setup/setup_screen.dart` :

- Ligne 5 : retirer `import '../../models/about.dart';` si plus référencé après les retraits ci-dessous (le sera, Step 5 le confirmera)
- Ligne 14 : retirer `import 'about/about_screen.dart';`
- Lignes 51-52 : retirer le compteur `int _aboutRefresh = 0;` et son commentaire
- Lignes 90-95 : retirer la méthode `_openAbout`
- Lignes 193-212 : retirer la méthode `_buildAboutCard`
- Ligne 241 : retirer la branche `9 => _buildAboutCard(),` du switch
- Ligne 280 : changer `itemCount: 9` → `itemCount: 8`

> Note : Setup ne référence plus AboutInfo après ces retraits. L'import `models/about.dart` peut sauter — `flutter analyze` te dira.

- [ ] **Step 5: `flutter analyze` clean**

```bash
cd app && flutter analyze
```
Expected: `No issues found!`. Si une remontée d'import unused, retire l'import.

- [ ] **Step 6: Tests Setup et About passent**

```bash
cd app && flutter test test/features/setup/ test/features/about/
```
Expected: tous verts.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(app): promote AboutScreen out of Setup feature

Spec Hub central : About devient feature racine accessible via Hub
(carte 4). Setup retrouve une sémantique pure 'configuration' :
itemCount 9 → 8, branche 9 retirée du switch, fichiers déplacés
features/setup/about/ → features/about/.

AstroScreen.about ajouté à l'enum.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5 — Créer le widget `HubCard` (TDD)

**Files:**
- Create: `app/lib/features/hub/widgets/hub_card.dart`
- Create: `app/test/features/hub/widgets/hub_card_test.dart`

- [ ] **Step 1: Écrire le test qui échoue**

Crée `app/test/features/hub/widgets/hub_card_test.dart` :

```dart
import 'package:astro_brain/features/hub/widgets/hub_card.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

ThemeData _testTheme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: const TextStyle(color: color.textPrimary),
    hudValue: const TextStyle(color: color.textPrimary),
    hudCaption: const TextStyle(color: color.textPrimary),
    hudBadge: const TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

Widget _wrap(Widget child) => MaterialApp(
      theme: _testTheme(),
      home: Scaffold(body: child),
    );

void main() {
  testWidgets('HubCard renders label, hint and hero icon', (tester) async {
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedTelescope01,
        label: 'SETUP',
        hint: 'Calibration · niveau · réseau',
        onTap: () {},
      ),
    ));

    expect(find.text('SETUP'), findsOneWidget);
    expect(find.text('Calibration · niveau · réseau'), findsOneWidget);
    expect(find.byIcon(HugeIcons.strokeRoundedTelescope01), findsOneWidget);
  });

  testWidgets('HubCard onTap is invoked', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedTelescope01,
        label: 'SETUP',
        hint: 'hint',
        onTap: () => taps++,
      ),
    ));

    await tester.tap(find.byType(HubCard));
    await tester.pumpAndSettle();

    expect(taps, 1);
  });

  testWidgets('HubCard primary variant shows chevron icon', (tester) async {
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedJoystick01,
        label: 'MANUEL',
        hint: 'Joystick',
        primary: true,
        onTap: () {},
      ),
    ));

    expect(
      find.byWidgetPredicate(
          (w) => w is PhosphorIcon && w.icon == PhosphorIconsBold.caretRight),
      findsOneWidget,
    );
  });
}
```

- [ ] **Step 2: Vérifier que le test échoue (le fichier n'existe pas encore)**

```bash
cd app && flutter test test/features/hub/widgets/hub_card_test.dart
```
Expected: échec à la compilation `Target of URI doesn't exist: 'package:astro_brain/features/hub/widgets/hub_card.dart'`.

- [ ] **Step 3: Implémenter le widget minimal**

Crée `app/lib/features/hub/widgets/hub_card.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';

/// Carte du Hub : hero icon + libellé + hint + chevron, pleine largeur.
/// Variant `primary` pour la première carte (gradient + glow accent).
class HubCard extends StatelessWidget {
  const HubCard({
    super.key,
    required this.heroIcon,
    required this.label,
    required this.hint,
    required this.onTap,
    this.primary = false,
  });

  final IconData heroIcon;
  final String label;
  final String hint;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final bgGradient = primary
        ? LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              colors.accent.withValues(alpha: 0.12),
              colors.accent.withValues(alpha: 0.04),
            ],
          )
        : null;
    final borderColor = primary
        ? colors.accent.withValues(alpha: 0.4)
        : colors.accent.withValues(alpha: 0.18);
    final iconBg = primary
        ? colors.accent.withValues(alpha: 0.2)
        : colors.accent.withValues(alpha: 0.1);
    final iconShadow = primary
        ? [
            BoxShadow(
              color: colors.accent.withValues(alpha: 0.3),
              blurRadius: 16,
            ),
          ]
        : <BoxShadow>[];

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusXL),
        child: Container(
          decoration: BoxDecoration(
            gradient: bgGradient,
            color: bgGradient == null
                ? colors.accent.withValues(alpha: 0.04)
                : null,
            border: Border.all(color: borderColor),
            borderRadius: BorderRadius.circular(DesignTokens.radiusXL),
          ),
          padding: const EdgeInsets.all(DesignTokens.spaceLG),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
                  boxShadow: iconShadow,
                ),
                child: Icon(
                  heroIcon,
                  color: colors.accent,
                  size: 28,
                ),
              ),
              const SizedBox(width: DesignTokens.spaceLG),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: text.hudLabel),
                    const SizedBox(height: 2),
                    Text(
                      hint,
                      style: text.hudCaption.copyWith(
                        color: colors.textMuted,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              PhosphorIcon(
                PhosphorIconsBold.caretRight,
                color: colors.accent.withValues(alpha: 0.4),
                size: DesignTokens.iconSizeMD,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
cd app && flutter test test/features/hub/widgets/hub_card_test.dart
```
Expected: 3 tests verts.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/hub/widgets/hub_card.dart app/test/features/hub/widgets/hub_card_test.dart
git commit -m "feat(app): HubCard widget for hub central"
```

---

## Task 6 — Créer `HubScreen` (TDD)

**Files:**
- Create: `app/lib/features/hub/hub_screen.dart`
- Create: `app/test/features/hub/hub_screen_test.dart`

- [ ] **Step 1: Écrire le test qui échoue**

Crée `app/test/features/hub/hub_screen_test.dart` :

```dart
import 'package:astro_brain/features/about/about_screen.dart';
import 'package:astro_brain/features/hub/hub_screen.dart';
import 'package:astro_brain/features/hub/widgets/hub_card.dart';
import 'package:astro_brain/features/manual/manual_screen.dart';
import 'package:astro_brain/features/setup/setup_screen.dart';
import 'package:astro_brain/features/system/system_screen.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:astro_brain/theme/theme_cubit.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockStream extends Mock implements EventStreamService {}

class _MockApi extends Mock implements ApiService {}

ThemeData _testTheme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: const TextStyle(color: color.textPrimary),
    hudValue: const TextStyle(color: color.textPrimary),
    hudCaption: const TextStyle(color: color.textPrimary),
    hudBadge: const TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

Widget _wrap(Widget child, AppBloc bloc, ThemeCubit theme, PiHost host) {
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>.value(value: host),
      RepositoryProvider<ApiService>(create: (_) => _MockApi()),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
    ],
    child: MultiBlocProvider(
      providers: [
        BlocProvider<AppBloc>.value(value: bloc),
        BlocProvider<ThemeCubit>.value(value: theme),
      ],
      child: MaterialApp(
        theme: _testTheme(),
        home: child,
      ),
    ),
  );
}

void main() {
  late _MockStream mockStream;
  late AppBloc bloc;
  late ThemeCubit theme;
  late PiHost host;

  setUp(() async {
    mockStream = _MockStream();
    when(() => mockStream.stream)
        .thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => mockStream.start()).thenAnswer((_) {});
    when(() => mockStream.stop()).thenAnswer((_) async {});
    when(() => mockStream.dispose()).thenAnswer((_) async {});

    bloc = AppBloc(eventStream: mockStream);
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    theme = ThemeCubit(prefs: prefs);
    host = const PiHost();
  });

  tearDown(() {
    bloc.close();
    theme.close();
  });

  testWidgets('HubScreen renders 4 cards in order', (tester) async {
    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host),
    );
    await tester.pump();

    final cards = tester.widgetList<HubCard>(find.byType(HubCard)).toList();
    expect(cards, hasLength(4));
    expect(cards[0].label, 'MANUEL');
    expect(cards[1].label, 'SETUP');
    expect(cards[2].label, 'STATUS');
    expect(cards[3].label, 'À PROPOS');
  });

  testWidgets('HubScreen first card is primary', (tester) async {
    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host),
    );
    await tester.pump();

    final cards = tester.widgetList<HubCard>(find.byType(HubCard)).toList();
    expect(cards[0].primary, isTrue);
    expect(cards[1].primary, isFalse);
    expect(cards[2].primary, isFalse);
    expect(cards[3].primary, isFalse);
  });

  testWidgets('HubScreen header shows title and overline', (tester) async {
    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host),
    );
    await tester.pump();

    expect(find.text('// ASTRO-BRAIN'), findsOneWidget);
    expect(find.text('Que fait-on ce soir ?'), findsOneWidget);
  });

  testWidgets('Tapping MANUEL pushes ManualScreen', (tester) async {
    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host),
    );
    await tester.pump();

    await tester.tap(find.text('MANUEL'));
    await tester.pumpAndSettle();

    expect(find.byType(ManualScreen), findsOneWidget);
  });

  testWidgets('Tapping SETUP pushes SetupScreen', (tester) async {
    // Setup uses ApiService.getCalibrationStatus / getAltLimits — stub them
    final apiMock = _MockApi();
    when(() => apiMock.getCalibrationStatus(any()))
        .thenAnswer((_) async => throw Exception('not under test'));
    when(() => apiMock.getAltLimits())
        .thenAnswer((_) async => throw Exception('not under test'));

    // Wrap with the apiMock instead of the default _MockApi
    await tester.pumpWidget(
      MultiRepositoryProvider(
        providers: [
          RepositoryProvider<PiHost>.value(value: host),
          RepositoryProvider<ApiService>.value(value: apiMock),
          RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
        ],
        child: MultiBlocProvider(
          providers: [
            BlocProvider<AppBloc>.value(value: bloc),
            BlocProvider<ThemeCubit>.value(value: theme),
          ],
          child: MaterialApp(
            theme: _testTheme(),
            home: const HubScreen(),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('SETUP'));
    await tester.pumpAndSettle();

    expect(find.byType(SetupScreen), findsOneWidget);
  });

  testWidgets('Tapping STATUS pushes SystemScreen', (tester) async {
    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host),
    );
    await tester.pump();

    await tester.tap(find.text('STATUS'));
    await tester.pumpAndSettle();

    expect(find.byType(SystemScreen), findsOneWidget);
  });

  testWidgets('Tapping À PROPOS pushes AboutScreen', (tester) async {
    final apiMock = _MockApi();
    when(() => apiMock.getAbout())
        .thenAnswer((_) async => throw Exception('not under test'));

    await tester.pumpWidget(
      MultiRepositoryProvider(
        providers: [
          RepositoryProvider<PiHost>.value(value: host),
          RepositoryProvider<ApiService>.value(value: apiMock),
          RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
        ],
        child: MultiBlocProvider(
          providers: [
            BlocProvider<AppBloc>.value(value: bloc),
            BlocProvider<ThemeCubit>.value(value: theme),
          ],
          child: MaterialApp(
            theme: _testTheme(),
            home: const HubScreen(),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('À PROPOS'));
    await tester.pumpAndSettle();

    expect(find.byType(AboutScreen), findsOneWidget);
  });
}
```

- [ ] **Step 2: Vérifier l'échec compilation**

```bash
cd app && flutter test test/features/hub/hub_screen_test.dart
```
Expected: échec — `HubScreen` introuvable.

- [ ] **Step 3: Implémenter `HubScreen`**

Crée `app/lib/features/hub/hub_screen.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';

import '../about/about_screen.dart';
import '../manual/manual_screen.dart';
import '../setup/setup_screen.dart';
import '../system/system_screen.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'widgets/hub_card.dart';

class HubScreen extends StatelessWidget {
  const HubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final entries = <_HubEntry>[
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedJoystick01,
        label: 'MANUEL',
        hint: 'Joystick · piloter la monture',
        primary: true,
        builder: (_) => const ManualScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedSettings02,
        label: 'SETUP',
        hint: 'Calibration · niveau · réseau',
        builder: (_) => const SetupScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedRadar01,
        label: 'STATUS',
        hint: 'Indicateurs · capteurs · mount',
        builder: (_) => const SystemScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedInformationCircle,
        label: 'À PROPOS',
        hint: 'Versions · uptime · système',
        builder: (_) => const AboutScreen(),
      ),
    ];

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
              const AstroAppBar(current: AstroScreen.hub),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  DesignTokens.spaceLG,
                  DesignTokens.space2XL,
                  DesignTokens.spaceLG,
                  DesignTokens.spaceLG,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '// ASTRO-BRAIN',
                      style: text.hudLabel.copyWith(
                        color: colors.accent.withValues(alpha: 0.6),
                      ),
                    ),
                    const SizedBox(height: DesignTokens.spaceXS),
                    Text(
                      'Que fait-on ce soir ?',
                      style: TextStyle(
                        fontSize: 18,
                        color: colors.textPrimary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(
                    horizontal: DesignTokens.spaceLG,
                  ),
                  itemCount: entries.length,
                  separatorBuilder: (_, __) =>
                      const SizedBox(height: DesignTokens.spaceMD),
                  itemBuilder: (ctx, i) {
                    final e = entries[i];
                    return HubCard(
                      heroIcon: e.heroIcon,
                      label: e.label,
                      hint: e.hint,
                      primary: e.primary,
                      onTap: () => Navigator.of(ctx).push(
                        MaterialPageRoute(builder: e.builder),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HubEntry {
  const _HubEntry({
    required this.heroIcon,
    required this.label,
    required this.hint,
    required this.builder,
    this.primary = false,
  });
  final IconData heroIcon;
  final String label;
  final String hint;
  final WidgetBuilder builder;
  final bool primary;
}
```

> ⚠️ Vérifier les noms d'icônes HugeIcons exacts. Si `strokeRoundedJoystick01` n'existe pas, fallback `strokeRoundedGameController01`. `strokeRoundedSettings02`, `strokeRoundedRadar01`, `strokeRoundedInformationCircle` doivent exister dans 1.1.6 — sinon adapter au plus proche (cf. liste : Constellation, Telescope01/02, Satellite01-03, Radar01/02, Orbit01/02, Comet, Galaxy, Asteroid, Solar System, Astronaut). Confirmation rapide :

```bash
cd app && grep -ohE "strokeRounded[A-Z][A-Za-z0-9]*" .dart_tool/package_config.json /dev/null 2>&1 || \
  grep -lE "strokeRounded(Joystick|GameController|Settings|Radar|Information|Telescope)" \
    .dart_tool/flutter_build/ 2>/dev/null || \
  echo "(pas de listing direct — itérer via flutter analyze)"
```

Si `flutter analyze` flag un identifiant manquant, choisis l'alternative la plus proche dans la liste fournie.

- [ ] **Step 4: Tests passent**

```bash
cd app && flutter test test/features/hub/hub_screen_test.dart
```
Expected: 7 tests verts.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/hub/hub_screen.dart app/test/features/hub/hub_screen_test.dart
git commit -m "feat(app): HubScreen — landing post-Splash with 4 cards

Macro 3 item #1 livré : Hub central avec MANUEL · SETUP · STATUS ·
À PROPOS en liste verticale. Première carte (MANUEL) en primary
variant. Hero icons HugeIcons stroke-rounded.

Pas encore wiré comme root — Task 7.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7 — Wire `HubScreen` comme racine post-Splash

**Files:**
- Modify: `app/lib/app.dart:6,88` — import `HubScreen`, `_RootRouterState.build` retourne `const HubScreen()`
- Modify: `app/test/widget_test.dart` (si présent et vérifie HomeScreen comme root)

- [ ] **Step 1: Édit `app.dart`**

Dans `app/lib/app.dart` :

- Ligne 6 : remplacer `import 'features/manual/manual_screen.dart';` par `import 'features/hub/hub_screen.dart';` (et garder `manual_bloc.dart` qui est ligne 5 — vérifier l'ordre exact post-Task 2).
- Ligne 88 : `return const ManualScreen();` → `return const HubScreen();`

> Vérification : après Task 2 le `manual_screen.dart` import était nécessaire ; il ne l'est plus ici. Idem si une référence `ManualScreen` ne subsiste pas dans `app.dart`, retire l'import.

- [ ] **Step 2: Vérifier `widget_test.dart`**

```bash
cat /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/app/test/widget_test.dart
```

Si le fichier est le boilerplate Flutter par défaut (compteur), il ne référence ni Home ni Hub — laisser tel quel. S'il a été personnalisé pour vérifier la landing, mettre à jour pour attendre `HubScreen` au lieu de `HomeScreen`.

- [ ] **Step 3: Lancer toute la suite de tests**

```bash
cd app && flutter test
```
Expected: tous verts.

- [ ] **Step 4: `flutter analyze` clean**

```bash
cd app && flutter analyze
```
Expected: `No issues found!`

- [ ] **Step 5: Commit**

```bash
git add app/lib/app.dart app/test/widget_test.dart
git commit -m "feat(app): wire HubScreen as root post-Splash

Splash → HubScreen (au lieu de ManualScreen). Hub central devient la
landing par défaut de l'app.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8 — Validation visuelle Android USB

**Files:** aucun (test manuel)

- [ ] **Step 1: Build et déploiement sur téléphone Android**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN/app
flutter devices
flutter run --release  # ou debug pour tester plus vite
```

- [ ] **Step 2: Parcours nominal**

- Splash s'affiche → Hub apparaît avec 4 cartes (MANUEL en primary, glow accent visible).
- Tap MANUEL → ManualScreen (joystick) s'ouvre. Back → Hub.
- Tap SETUP → SetupScreen (8 cartes, plus de carte About). Back → Hub.
- Tap STATUS → SystemScreen (subsystem cards). Back → Hub.
- Tap À PROPOS → AboutScreen (versions, uptime). Back → Hub.
- Toggle thème jour/nuit dans l'AppBar : Hub passe en rouge HUD lisible.
- Tap pastille `overall` AppBar → SystemScreen (raccourci, équivalent carte STATUS).

- [ ] **Step 3: Capture d'écran jour + nuit du Hub**

Place les screenshots dans `docs/product/features/hub/` (créer le dossier) :
- `hub-day.png`
- `hub-night.png`

```bash
mkdir -p docs/product/features/hub
# Ajouter les screenshots manuellement via adb pull ou flutter screenshot
```

- [ ] **Step 4: Commit screenshots**

```bash
git add docs/product/features/hub/
git commit -m "docs(hub): screenshots day/night Hub central"
```

---

## Task 9 — Documentation

**Files:**
- Create: `docs/product/features/hub.md`
- Modify: `docs/project/roadmap.md` — Macro 3 item #1 statut livré
- Modify: `docs/project/journal.md` — Session 20

- [ ] **Step 1: Fiche feature Hub**

Crée `docs/product/features/hub.md` :

```markdown
# Hub central

Landing post-Splash de l'app. Index visuel des features livrées,
grandit avec le train.

## État

Livré : 2026-05-08 (Macro 3 item #1).

## Comportement

- Apparaît immédiatement après le Splash, en lieu et place de l'ancien
  HomeScreen (joystick).
- 4 cartes en liste verticale : MANUEL · SETUP · STATUS · À PROPOS.
- Première carte (MANUEL) en primary variant : gradient accent + glow
  doux sur le hero icon.
- AppBar partagée présente : pastille `overall`, gear Setup, toggle
  thème, reconnect conditionnel.

## Stratégie évolutive

Le Hub n'affiche que les features **vivantes**. Pas de cartes
"Coming soon". Quand une nouvelle feature de premier niveau est
livrée (Wizard 3-étoiles, GoTo, Catalogue), elle s'ajoute comme
nouvelle carte.

Ordre indicatif des prochaines additions (Macro 3) :
- WIZARD ALIGNEMENT — `HugeIcons.strokeRoundedConstellation`
- GOTO — hero icon à choisir
- CATALOGUE — hero icon à choisir

Au-delà de ~6-7 cartes, réévaluer le layout (section, grille).

## Architecture

- `app/lib/features/hub/hub_screen.dart` — StatelessWidget, ListView
  de 4 `HubCard`. Pas de BLoC : tout est statique.
- `app/lib/features/hub/widgets/hub_card.dart` — widget réutilisable
  hero icon + label + hint + chevron.

Routing root : `app/lib/app.dart::_RootRouter` retourne `HubScreen`.

## Liens

- Spec : [`docs/superpowers/specs/2026-05-08-hub-central-design.md`](../../superpowers/specs/2026-05-08-hub-central-design.md)
- Plan : [`docs/superpowers/plans/2026-05-08-hub-central-implementation.md`](../../superpowers/plans/2026-05-08-hub-central-implementation.md)
- Design system (icônes) : [`design-system.md`](../design-system.md)
```

- [ ] **Step 2: Mettre à jour la roadmap**

Édite `docs/project/roadmap.md` : trouver la section Macro 3, marquer item #1 (Hub central) comme livré 2026-05-08. Format à respecter selon les autres items.

- [ ] **Step 3: Entrée journal Session 20**

Ajoute une nouvelle entrée en haut de `docs/project/journal.md` :

```markdown
## 2026-05-08 — Session 20 : Hub central (Macro 3 item #1)

**Livré** : Hub central remplace HomeScreen comme landing post-Splash.
4 cartes liste verticale (MANUEL · SETUP · STATUS · À PROPOS), hero
icons HugeIcons stroke-rounded, première carte en primary variant.

**Refactors associés** :
- `features/home/` → `features/manual/` (HomeScreen→ManualScreen,
  HomeBloc→ManualBloc, etc.).
- `features/setup/about/` → `features/about/` : About sort de Setup,
  promu feature racine.
- Enum `AstroScreen` : `home` retiré, `hub`, `manual`, `about` ajoutés.

**Décision** : Hub évolutif (pas anticipateur). Pas de cartes
"Coming soon" — chaque feature livrée ajoute sa carte au moment
d'arriver.

**Dépendances** : `hugeicons: ^1.1.6` ajouté en parenthèse pour
fournir le vocabulaire astro (telescope, satellite, radar, orbit,
constellation…). Convention double set documentée :
`design-system.md`. Phosphor reste pour l'UI utilitaire, HugeIcons
pour les hero icons domaine.
```

- [ ] **Step 4: Commit doc**

```bash
git add docs/product/features/hub.md docs/project/roadmap.md docs/project/journal.md
git commit -m "docs(hub): feature card + roadmap + journal session 20"
```

---

## Task 10 — Pull Request

- [ ] **Step 1: Push de la branche**

```bash
cd /home/pascal-lopez/PLOPEZ/PERSO/ASTRO-BRAIN
git push -u origin feat/macro3-hub-central
```

- [ ] **Step 2: Créer la PR via gh**

```bash
gh pr create --title "feat(app): Hub central — Macro 3 item #1" --body "$(cat <<'EOF'
## Summary
- Hub central remplace HomeScreen comme landing post-Splash, avec 4 cartes (MANUEL · SETUP · STATUS · À PROPOS) en liste verticale.
- Refactors associés : `features/home/` → `features/manual/` ; `features/setup/about/` → `features/about/` (About promu feature racine).
- Enum `AstroScreen` : `home` retiré, `hub`/`manual`/`about` ajoutés.

## Test plan
- [ ] `flutter analyze` clean
- [ ] `flutter test` tous verts (incluant `test/features/hub/`, `test/features/manual/`, `test/features/about/`)
- [ ] Validation Android USB : Hub s'affiche post-Splash, navigation 4 cartes OK, retour à Hub OK
- [ ] Toggle thème jour/nuit lisible
- [ ] Pastille `overall` AppBar route vers SystemScreen
- [ ] Screenshots day/night ajoutés dans `docs/product/features/hub/`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Récupérer l'URL et la transmettre à l'utilisateur**

---

## Self-Review (effectuée à l'écriture du plan)

**Spec coverage** :
- HubScreen + 4 cartes : Tasks 5, 6
- Hub évolutif : Task 6 (entries const, pas de "coming soon")
- AppBar conservée : Tasks 5, 6 (assemblée dans HubScreen)
- Routing root Splash → Hub : Task 7
- Rename Home → Manual : Task 2
- About hors Setup : Task 4
- Enum AstroScreen mis à jour : Tasks 1, 3, 4
- Tests unitaires (HubCard, HubScreen, navigation) : Tasks 5, 6
- Validation Android USB : Task 8
- Doc (feature card, roadmap, journal) : Task 9
- Plan de livraison : conforme spec (slice unique, une PR — Task 10)
- Hors scope (Wizard, GoTo, Catalogue, refonte écrans cibles) : respecté

**Placeholders** : aucun TBD/TODO. Code complet dans chaque step. Noms HugeIcons annotés avec fallback explicite.

**Type consistency** : `HubCard` props (heroIcon, label, hint, primary, onTap) constants entre Tasks 5 et 6. `_HubEntry` privé à `hub_screen.dart`. `AstroScreen` valeurs cohérentes entre tasks (hub, manual, system, setup, about).
