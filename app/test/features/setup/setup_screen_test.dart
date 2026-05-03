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

Widget _wrap(Widget child, AppBloc bloc, ThemeCubit theme) {
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>(create: (_) => const PiHost()),
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

    await tester.pumpWidget(_wrap(const SetupScreen(), bloc, theme));
    await tester.pump();

    expect(find.byType(SetupCard), findsNWidgets(9));
  });

  testWidgets('only card #8 (RÉSEAU) has onTap', (tester) async {
    tester.view.physicalSize = const Size(1080, 4000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_wrap(const SetupScreen(), bloc, theme));
    await tester.pump();

    final cards = tester.widgetList<SetupCard>(find.byType(SetupCard)).toList();
    for (var i = 0; i < cards.length; i++) {
      final isNetwork = (i == 7); // 0-based → card #8
      expect(
        cards[i].onTap == null,
        !isNetwork,
        reason: 'card #${i + 1} onTap mismatch',
      );
    }
  });
}
