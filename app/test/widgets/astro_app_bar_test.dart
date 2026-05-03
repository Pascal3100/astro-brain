import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart'; // AppTextStyles
import 'package:astro_brain/theme/theme_cubit.dart';
import 'package:astro_brain/widgets/astro_app_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockStream extends Mock implements EventStreamService {}

class _MockApi extends Mock implements ApiService {}

// Minimal ThemeData carrying the AppColors+AppTextStyles extensions.
// Uses plain TextStyle to avoid GoogleFonts HTTP requests in test environment.
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
        home: Scaffold(body: child),
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

  testWidgets('renders gear icon and theme toggle on home', (tester) async {
    await tester.pumpWidget(
      _wrap(const AstroAppBar(current: AstroScreen.home), bloc, theme, host),
    );
    await tester.pump();

    // Gear icon present
    expect(
      find.byWidgetPredicate(
          (w) => w is PhosphorIcon && w.icon == PhosphorIconsBold.gearSix),
      findsOneWidget,
    );
    // Theme toggle: sun or moon
    final hasSun = find
        .byWidgetPredicate(
            (w) => w is PhosphorIcon && w.icon == PhosphorIconsBold.sun)
        .evaluate()
        .isNotEmpty;
    final hasMoon = find
        .byWidgetPredicate(
            (w) => w is PhosphorIcon && w.icon == PhosphorIconsBold.moon)
        .evaluate()
        .isNotEmpty;
    expect(hasSun || hasMoon, isTrue);
  });

  testWidgets('gear icon disabled when current is setup', (tester) async {
    await tester.pumpWidget(
      _wrap(const AstroAppBar(current: AstroScreen.setup), bloc, theme, host),
    );
    await tester.pump();

    // Find the IconButton whose icon is gearSix
    final gearButtons = tester.widgetList<IconButton>(find.byType(IconButton));
    final gearButton = gearButtons.firstWhere(
      (btn) {
        if (btn.icon is PhosphorIcon) {
          return (btn.icon as PhosphorIcon).icon == PhosphorIconsBold.gearSix;
        }
        return false;
      },
      orElse: () => throw StateError('Gear IconButton not found'),
    );
    expect(gearButton.onPressed, isNull);
  });
}
