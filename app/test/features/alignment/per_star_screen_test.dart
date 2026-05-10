import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/screens/per_star_screen.dart';
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

StarDto _vega() => const StarDto(
      id: 'vega',
      name: 'Vega',
      bayer: 'α Lyrae',
      raDeg: 279.234,
      decDeg: 38.784,
      mag: 0.03,
    );

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

  testWidgets('PerStarScreen displays hero name + coords + magnitude',
      (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    await t.pumpWidget(_wrap(
      PerStarScreen(
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
}
