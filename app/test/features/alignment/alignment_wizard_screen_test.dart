import 'package:astro_brain/features/alignment/alignment_bloc.dart';
import 'package:astro_brain/features/alignment/alignment_state.dart';
import 'package:astro_brain/features/alignment/alignment_wizard_screen.dart';
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

class _MockBloc extends Mock implements AlignmentBloc {}

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

Widget _wrap(
  Widget child,
  AlignmentBloc alignBloc,
  AppBloc appBloc,
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
        BlocProvider<AlignmentBloc>.value(value: alignBloc),
        BlocProvider<AppBloc>.value(value: appBloc),
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
  late AppBloc appBloc;
  late ThemeCubit theme;
  late PiHost host;

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
  });

  tearDown(() {
    appBloc.close();
    theme.close();
  });

  testWidgets('Idle state shows IntroScreen', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    final bloc = _MockBloc();
    when(() => bloc.state).thenReturn(const AlignmentIdle());
    when(() => bloc.stream).thenAnswer((_) => const Stream.empty());

    await t.pumpWidget(_wrap(
      const AlignmentWizardScreen(),
      bloc,
      appBloc,
      theme,
      host,
    ));
    await t.pump();

    expect(find.text('ALIGNEMENT'), findsWidgets);
  });

  testWidgets('Done state shows DoneScreen', (t) async {
    t.view.physicalSize = const Size(1080, 4000);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    final bloc = _MockBloc();
    when(() => bloc.state).thenReturn(const AlignmentDone());
    when(() => bloc.stream).thenAnswer((_) => const Stream.empty());

    await t.pumpWidget(_wrap(
      const AlignmentWizardScreen(),
      bloc,
      appBloc,
      theme,
      host,
    ));
    await t.pump();

    expect(find.textContaining('ALIGNÉE'), findsOneWidget);
  });
}
