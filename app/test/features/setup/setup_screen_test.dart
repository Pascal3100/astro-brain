import 'package:astro_brain/features/setup/setup_screen.dart';
import 'package:astro_brain/features/setup/widgets/setup_card.dart';
import 'package:astro_brain/models/calibration.dart';
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
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

Widget _wrap(Widget child, AppBloc bloc, ThemeCubit theme, {ApiService? api}) {
  final apiInstance = api ?? _MockApi();
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>(create: (_) => const PiHost()),
      RepositoryProvider<ApiService>(create: (_) => apiInstance),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
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
    // Par défaut, capteur jamais calibré (FutureBuilder card #1).
    when(() => mockApi.getCalibrationStatus(any())).thenAnswer(
      (_) async => const CalibrationStatus(
        sensorId: 'adxl345_mount',
        calibratedAt: null,
        payload: null,
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

  testWidgets('renders 9 SetupCards', (tester) async {
    // Tall viewport so ListView.separated builds all 9 items.
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      _wrap(const SetupScreen(), bloc, theme, api: mockApi),
    );
    // Laisse le FutureBuilder se résoudre sans attendre les animations infinies.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byType(SetupCard), findsNWidgets(9));
  });

  testWidgets(
    'cards #1 (NIVEAU MONTURE), #2 (COMPASS) and #8 (RÉSEAU) have onTap',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 4000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        _wrap(const SetupScreen(), bloc, theme, api: mockApi),
      );
      // Laisse les FutureBuilder se résoudre sans attendre les animations infinies.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      final cards = tester
          .widgetList<SetupCard>(find.byType(SetupCard))
          .toList();
      for (var i = 0; i < cards.length; i++) {
        final isInteractive = (i == 0) || (i == 1) || (i == 7);
        expect(
          cards[i].onTap == null,
          !isInteractive,
          reason: 'card #${i + 1} onTap mismatch',
        );
      }
      // Sanity : le mock a bien été appelé pour les deux capteurs câblés.
      verify(() => mockApi.getCalibrationStatus('adxl345_mount')).called(1);
      verify(() => mockApi.getCalibrationStatus('lis3mdl')).called(1);
    },
  );

  testWidgets(
    'cards #1 and #2 sublabel read "Non calibré" when never calibrated',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 4000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        _wrap(const SetupScreen(), bloc, theme, api: mockApi),
      );
      // Laisse les FutureBuilder se résoudre sans attendre les animations infinies.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('Non calibré'), findsNWidgets(2));
    },
  );

  test('formatRelativeAge formats durations correctly', () {
    expect(formatRelativeAge(const Duration(seconds: 5)), 'Calibré il y a 5s');
    expect(
      formatRelativeAge(const Duration(minutes: 2)),
      'Calibré il y a 2min',
    );
    expect(formatRelativeAge(const Duration(hours: 3)), 'Calibré il y a 3h');
    expect(formatRelativeAge(const Duration(days: 4)), 'Calibré il y a 4j');
  });
}
