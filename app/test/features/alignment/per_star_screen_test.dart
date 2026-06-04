import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/features/alignment/screens/per_star_screen.dart';
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

// Minimal ThemeData carrying the AppColors + AppTextStyles extensions.
// Plain TextStyle to avoid GoogleFonts HTTP requests during tests.
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

Widget _wrap(
  Widget child,
  AppBloc bloc,
  ThemeCubit theme,
  PiHost host,
) {
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

StarDto _vega() => const StarDto(
      id: 'vega',
      name: 'Vega',
      bayer: 'α Lyrae',
      raDeg: 279.234,
      decDeg: 38.784,
      mag: 0.03,
    );

StarDto _dubhe() => const StarDto(
      id: 'dubhe',
      name: 'Dubhe',
      bayer: 'α UMa',
      raDeg: 165.932,
      decDeg: 61.751,
      mag: 1.79,
    );

ConstellationFigureDto _umaFigure() => ConstellationFigureDto(
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
      segments: const [
        [0, 1],
      ],
    );

void main() {
  late _MockStream mockStream;
  late AppBloc bloc;
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

    bloc = AppBloc(eventStream: mockStream);

    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    theme = ThemeCubit(prefs: prefs);

    host = const PiHost();
    mockRepo = _MockRepo();
  });

  tearDown(() {
    bloc.close();
    theme.close();
  });

  testWidgets('PerStarScreen displays hero name + coords + magnitude',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 1,
        totalSteps: 3,
        target: _vega(),
        targetAz: 248.0,
        targetAlt: 42.0,
        currentAz: 246.2,
        currentAlt: 43.3,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    expect(find.text('VEGA'), findsOneWidget);
    expect(find.textContaining('mag 0.03'), findsOneWidget);
    expect(find.textContaining('AZ 248'), findsOneWidget);
  });

  testWidgets('Tap CENTRÉ triggers onCentered', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    bool tapped = false;
    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 1,
        totalSteps: 3,
        target: _vega(),
        targetAz: 248.0,
        targetAlt: 42.0,
        currentAz: 246.0,
        currentAlt: 43.0,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () => tapped = true,
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    await t.tap(find.text('CENTRÉ ✓'));
    expect(tapped, isTrue);
  });

  testWidgets('Hero shows constellation name for known abbr', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 2,
        totalSteps: 3,
        target: _dubhe(),
        targetAz: 312.0,
        targetAlt: 47.0,
        currentAz: 310.0,
        currentAlt: 46.0,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    // Full constellation name should appear in the hero area.
    expect(find.textContaining('GRANDE OURSE'), findsOneWidget);
  });

  testWidgets(
      '"Voir dans la constellation" button is present for star with known abbr',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 2,
        totalSteps: 3,
        target: _dubhe(),
        targetAz: 312.0,
        targetAlt: 47.0,
        currentAz: 310.0,
        currentAlt: 46.0,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    expect(find.textContaining('constellation'), findsOneWidget);
  });

  testWidgets(
      'Tapping "Voir dans la constellation" opens bottom sheet with ConstellationChart',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(
      () => mockRepo.fetchConstellation(
        any(),
        raDeg: any(named: 'raDeg'),
        decDeg: any(named: 'decDeg'),
      ),
    ).thenAnswer((_) async => _umaFigure());

    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 2,
        totalSteps: 3,
        target: _dubhe(),
        targetAz: 312.0,
        targetAlt: 47.0,
        currentAz: 310.0,
        currentAlt: 46.0,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    await t.tap(find.textContaining('constellation'));
    // Let the async future complete then render the bottom sheet.
    await t.pump();
    await t.pump(const Duration(milliseconds: 100));

    expect(find.byType(ConstellationChart), findsOneWidget);

    // Verify repo was called with correct args.
    verify(
      () => mockRepo.fetchConstellation(
        'UMa',
        raDeg: 165.932,
        decDeg: 61.751,
      ),
    ).called(1);
  });

  testWidgets(
      'Shows SnackBar when fetchConstellation throws', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    when(
      () => mockRepo.fetchConstellation(
        any(),
        raDeg: any(named: 'raDeg'),
        decDeg: any(named: 'decDeg'),
      ),
    ).thenThrow(Exception('404 not found'));

    await t.pumpWidget(_wrap(
      PerStarScreen(
        repo: mockRepo,
        stepIndex: 2,
        totalSteps: 3,
        target: _dubhe(),
        targetAz: 312.0,
        targetAlt: 47.0,
        currentAz: 310.0,
        currentAlt: 46.0,
        rate: 4,
        onPress: (_) {},
        onRelease: () {},
        onRateChanged: (_) {},
        onCentered: () {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    await t.tap(find.textContaining('constellation'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 100));

    expect(find.byType(ConstellationChart), findsNothing);
    expect(
      find.textContaining('Schéma indisponible'),
      findsOneWidget,
    );
  });
}
