import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/features/alignment/screens/star_navigator_screen.dart';
import 'package:astro_brain/features/alignment/widgets/constellation_chart.dart';
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

class _MockRepo extends Mock implements AlignmentRepository {}

ThemeData _testTheme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(
    extensions: <ThemeExtension<dynamic>>[color, styles],
  );
}

Widget _wrap(Widget child, AppBloc appBloc, ThemeCubit theme, PiHost host) {
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>.value(value: host),
      RepositoryProvider<ApiService>(create: (_) => _MockApi()),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
    ],
    child: MultiBlocProvider(
      providers: [
        BlocProvider<AppBloc>.value(value: appBloc),
        BlocProvider<ThemeCubit>.value(value: theme),
      ],
      child: MaterialApp(theme: _testTheme(), home: child),
    ),
  );
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

StarDto _dubhe() => const StarDto(
      id: 'dubhe',
      name: 'Dubhe',
      bayer: 'α UMa',
      raDeg: 165.932,
      decDeg: 61.751,
      mag: 1.79,
    );

StarDto _vega() => const StarDto(
      id: 'vega',
      name: 'Vega',
      bayer: 'α Lyr',
      raDeg: 279.234,
      decDeg: 38.784,
      mag: 0.03,
    );

ConstellationFigureDto _umaFigure() => const ConstellationFigureDto(
      abbr: 'UMa',
      name: 'Grande Ourse',
      oriented: false,
      nodes: [
        ConstellationNodeDto(
          label: 'Dubhe',
          mag: 1.79,
          raDeg: 165.9,
          decDeg: 61.7,
          isTarget: true,
        ),
        ConstellationNodeDto(
          label: 'Merak',
          mag: 2.37,
          raDeg: 165.4,
          decDeg: 56.3,
          isTarget: false,
        ),
      ],
      segments: [[0, 1]],
    );

Map<String, List<StarDto>> _visibleStars() => {
      'UMa': [_dubhe()],
      'Lyr': [_vega()],
    };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  late _MockStream mockStream;
  late AppBloc appBloc;
  late ThemeCubit theme;
  late PiHost host;
  late _MockRepo mockRepo;

  setUp(() async {
    mockStream = _MockStream();
    when(() => mockStream.stream)
        .thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => mockStream.start()).thenAnswer((_) {});
    when(() => mockStream.stop()).thenAnswer((_) async {});
    when(() => mockStream.dispose()).thenAnswer((_) async {});

    appBloc = AppBloc(eventStream: mockStream);

    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    theme = ThemeCubit(prefs: prefs);

    host = const PiHost();
    mockRepo = _MockRepo();
  });

  tearDown(() {
    appBloc.close();
    theme.close();
  });

  // ---------------------------------------------------------------------------
  // Helper : pumpe le widget + laisse le Future de _load() se résoudre.
  // ---------------------------------------------------------------------------

  /// Après pumpWidget, l'initState lance _load() qui est async.
  /// On pumpe une première frame (animation), on attend la microtask queue
  /// avec pump(Duration.zero), puis on pumpe une seconde frame pour que
  /// setState() s'applique.
  Future<void> pumpScreen(WidgetTester t, Widget w) async {
    await t.pumpWidget(w);
    await t.pump(); // premier frame
    await t.pump(const Duration(milliseconds: 50)); // résolution du Future
  }

  // ---------------------------------------------------------------------------

  testWidgets('displays constellation labels after load', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenAnswer((_) async => _visibleStars());

    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(repository: mockRepo, onSelected: (_) {}),
        appBloc,
        theme,
        host,
      ),
    );

    // The selected constellation label (first alphabetically = Grande Ourse)
    // appears in the dropdown button.
    expect(find.textContaining('Grande Ourse'), findsWidgets);

    // Open the dropdown to verify Lyre also appears as an item.
    await t.tap(find.byType(DropdownButton<String>).first);
    await t.pump();
    expect(find.textContaining('Lyre'), findsWidgets);
  });

  testWidgets('star list shows stars of selected constellation', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenAnswer((_) async => _visibleStars());

    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(repository: mockRepo, onSelected: (_) {}),
        appBloc,
        theme,
        host,
      ),
    );

    // The first constellation alphabetically by full name is selected by
    // default; either star should appear once.
    final starNames = ['Dubhe', 'Vega'];
    final anyFound =
        starNames.any((n) => find.textContaining(n).evaluate().isNotEmpty);
    expect(anyFound, isTrue);
  });

  testWidgets('tapping a star shows ConstellationChart inline', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenAnswer((_) async => _visibleStars());
    when(
      () => mockRepo.fetchConstellation(
        any(),
        raDeg: any(named: 'raDeg'),
        decDeg: any(named: 'decDeg'),
      ),
    ).thenAnswer((_) async => _umaFigure());

    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(repository: mockRepo, onSelected: (_) {}),
        appBloc,
        theme,
        host,
      ),
    );

    // Select UMa if Lyre is shown first ("Grande Ourse" < "Lyre" alphabetically,
    // so UMa should be selected by default). Guard just in case.
    if (find.textContaining('Dubhe').evaluate().isEmpty) {
      await t.tap(find.byType(DropdownButton<String>).first);
      await t.pump();
      await t.tap(find.textContaining('Grande Ourse').last);
      await t.pump();
    }

    // Tap the Dubhe star tile.
    await t.tap(find.textContaining('Dubhe').first);
    // Let the async fetchConstellation complete.
    await t.pump();
    await t.pump(const Duration(milliseconds: 50));

    // ConstellationChart should appear inline (no bottom sheet needed).
    expect(find.byType(ConstellationChart), findsOneWidget);
  });

  testWidgets(
      '"Choisir cette étoile" button calls onSelected with correct star',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenAnswer((_) async => _visibleStars());
    when(
      () => mockRepo.fetchConstellation(
        any(),
        raDeg: any(named: 'raDeg'),
        decDeg: any(named: 'decDeg'),
      ),
    ).thenAnswer((_) async => _umaFigure());

    StarDto? selected;
    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(
          repository: mockRepo,
          onSelected: (s) => selected = s,
        ),
        appBloc,
        theme,
        host,
      ),
    );

    // Switch to Grande Ourse if needed.
    if (find.textContaining('Dubhe').evaluate().isEmpty) {
      await t.tap(find.byType(DropdownButton<String>).first);
      await t.pump();
      await t.tap(find.textContaining('Grande Ourse').last);
      await t.pump();
    }

    // Tap Dubhe to select it and load chart inline.
    await t.tap(find.textContaining('Dubhe').first);
    await t.pump();
    await t.pump(const Duration(milliseconds: 50));

    // Tap "Choisir cette étoile" — button is now in the main scroll area.
    await t.tap(find.text('CHOISIR CETTE ÉTOILE'));
    await t.pump();

    expect(selected, equals(_dubhe()));
  });

  testWidgets('fetchVisibleStars error shows error message', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenThrow(Exception('réseau indisponible'));

    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(repository: mockRepo, onSelected: (_) {}),
        appBloc,
        theme,
        host,
      ),
    );

    expect(find.textContaining('réseau indisponible'), findsOneWidget);
  });

  testWidgets('fetchConstellation error shows SnackBar', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(() => mockRepo.fetchVisibleStars())
        .thenAnswer((_) async => _visibleStars());
    when(
      () => mockRepo.fetchConstellation(
        any(),
        raDeg: any(named: 'raDeg'),
        decDeg: any(named: 'decDeg'),
      ),
    ).thenThrow(Exception('timeout'));

    await pumpScreen(
      t,
      _wrap(
        StarNavigatorScreen(repository: mockRepo, onSelected: (_) {}),
        appBloc,
        theme,
        host,
      ),
    );

    // Switch to Grande Ourse if needed.
    if (find.textContaining('Dubhe').evaluate().isEmpty) {
      await t.tap(find.byType(DropdownButton<String>).first);
      await t.pump();
      await t.tap(find.textContaining('Grande Ourse').last);
      await t.pump();
    }

    await t.tap(find.textContaining('Dubhe').first);
    await t.pump();
    await t.pump(const Duration(milliseconds: 50));

    expect(find.byType(ConstellationChart), findsNothing);
    expect(find.textContaining('Schéma indisponible'), findsOneWidget);
  });
}
