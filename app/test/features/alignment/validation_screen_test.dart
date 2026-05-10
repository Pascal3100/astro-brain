import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/screens/validation_screen.dart';
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
  return ThemeData(
    extensions: <ThemeExtension<dynamic>>[color, styles],
  );
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

AlignmentModelDto _modelWithOutlier() => const AlignmentModelDto(
      recordedStars: [],
      rmsArcmin: 5.4,
      residuals: {'sirius': 2.1, 'vega': 11.4, 'capella': 2.8},
      validatedAtUtc: '2026-05-09T22:00:00+00:00',
      quality: 'good',
    );

List<StarDto> _candidates() => const [
      StarDto(
        id: 'sirius',
        name: 'Sirius',
        bayer: 'α CMa',
        raDeg: 0,
        decDeg: 0,
        mag: 0,
      ),
      StarDto(
        id: 'vega',
        name: 'Vega',
        bayer: 'α Lyr',
        raDeg: 0,
        decDeg: 0,
        mag: 0,
      ),
      StarDto(
        id: 'capella',
        name: 'Capella',
        bayer: 'α Aur',
        raDeg: 0,
        decDeg: 0,
        mag: 0,
      ),
    ];

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

  testWidgets('ValidationScreen shows RMS + 3 residuals + diagnostic',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(_wrap(
      ValidationScreen(
        model: _modelWithOutlier(),
        candidates: _candidates(),
        onAccept: () {},
        onRestartStar: (_) {},
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    expect(find.textContaining('5.4'), findsWidgets);
    expect(find.textContaining('2.1'), findsOneWidget);
    expect(find.textContaining('11.4'), findsOneWidget);
    expect(find.textContaining('2.8'), findsOneWidget);
    expect(find.textContaining('VEGA'), findsWidgets);
    expect(find.text('ACCEPTER'), findsOneWidget);
    expect(find.textContaining('REFAIRE'), findsOneWidget);
  });

  testWidgets('Tap REFAIRE triggers onRestartStar with outlier idx',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    int? idx;
    await t.pumpWidget(_wrap(
      ValidationScreen(
        model: _modelWithOutlier(),
        candidates: _candidates(),
        onAccept: () {},
        onRestartStar: (i) => idx = i,
      ),
      bloc,
      theme,
      host,
    ));
    await t.pump();

    await t.tap(find.textContaining('REFAIRE'));
    expect(idx, 1); // vega est idx 1
  });
}
