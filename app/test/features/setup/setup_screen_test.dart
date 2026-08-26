import 'package:astro_brain/features/setup/reference/reference_models.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/features/setup/setup_screen.dart';
import 'package:astro_brain/features/setup/widgets/setup_card.dart';
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

class _MockRefRepo extends Mock implements ReferenceRepository {}

ThemeData _testTheme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

Widget _wrap(
  Widget child,
  AppBloc bloc,
  ThemeCubit theme, {
  ApiService? api,
  ReferenceRepository? refRepo,
}) {
  final apiInstance = api ?? _MockApi();
  final refRepoInstance = refRepo ?? _MockRefRepo();
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>(create: (_) => const PiHost()),
      RepositoryProvider<ApiService>(create: (_) => apiInstance),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
      RepositoryProvider<ReferenceRepository>(create: (_) => refRepoInstance),
    ],
    child: MultiBlocProvider(
      providers: [
        BlocProvider<AppBloc>.value(value: bloc),
        BlocProvider<ThemeCubit>.value(value: theme),
      ],
      child: MaterialApp(theme: _testTheme(), home: child),
    ),
  );
}

void main() {
  late _MockStream mockStream;
  late _MockApi mockApi;
  late _MockRefRepo refRepo;
  late AppBloc bloc;
  late ThemeCubit theme;

  setUp(() async {
    mockStream = _MockStream();
    when(
      () => mockStream.stream,
    ).thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => mockStream.start()).thenAnswer((_) {});
    when(() => mockStream.stop()).thenAnswer((_) async {});
    when(() => mockStream.dispose()).thenAnswer((_) async {});

    mockApi = _MockApi();
    // Par défaut, aucun site d'observation réglé (FutureBuilder card #1) :
    // `GET /site` répond 200 + `null`, d'où `getJsonOrNull`.
    when(() => mockApi.getJsonOrNull(any())).thenAnswer((_) async => null);

    refRepo = _MockRefRepo();
    // Par défaut, almanach prêt (FutureBuilder card #6).
    when(() => refRepo.getStatus()).thenAnswer(
      (_) async => const ReferenceStatusDto(
        ready: true,
        generatedAt: '2026-08-01T00:00:00+00:00',
        windowStart: '2026-08-01',
        windowEnd: '2026-09-30',
      ),
    );

    bloc = AppBloc(eventStream: mockStream);

    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    theme = ThemeCubit(prefs: prefs);
  });

  tearDown(() {
    bloc.close();
    theme.close();
  });

  testWidgets('renders 6 SetupCards', (tester) async {
    // Tall viewport so ListView.separated builds all 6 items.
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    // Laisse le FutureBuilder se résoudre sans attendre les animations infinies.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byType(SetupCard), findsNWidgets(6));
  });

  testWidgets(
      'card #1 (SITE), #5 (RÉSEAU) and #6 (ALMANACH) have onTap',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    // Laisse les FutureBuilder se résoudre sans attendre les animations infinies.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    final cards = tester
        .widgetList<SetupCard>(find.byType(SetupCard))
        .toList();
    for (var i = 0; i < cards.length; i++) {
      final isInteractive = (i == 0) || (i == 4) || (i == 5);
      expect(
        cards[i].onTap == null,
        !isInteractive,
        reason: 'card #${i + 1} onTap mismatch',
      );
    }
    // Sanity : la tuile a bien interrogé le backend pour le site.
    verify(() => mockApi.getJsonOrNull('/site')).called(1);
  });

  testWidgets('card #1 sublabel reads "Non défini" when no site is set', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    // Laisse les FutureBuilder se résoudre sans attendre les animations infinies.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Non défini'), findsOneWidget);
  });

  testWidgets('tuile ALMANACH affiche la fenêtre couverte quand prête', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('ALMANACH'), findsOneWidget);
    expect(find.textContaining('2026-09-30'), findsOneWidget);
  });

  testWidgets(
      'tuile ALMANACH indique « resynchroniser » quand pas prête',
      (tester) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    when(() => refRepo.getStatus())
        .thenAnswer((_) async => const ReferenceStatusDto(ready: false));

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.textContaining('resynchroniser'), findsOneWidget);
  });

  testWidgets('card #1 sublabel affiche les coordonnées du site connu', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    when(() => mockApi.getJsonOrNull(any())).thenAnswer(
      (_) async => {
        'lat': 43.6045,
        'lon': 1.4442,
        'set_at': '2026-08-26T20:00:00+00:00',
      },
    );

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi, refRepo: refRepo),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('43.60450°, 1.44420°'), findsOneWidget);
  });
}
