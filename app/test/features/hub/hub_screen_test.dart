import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/features/about/about_screen.dart';
import 'package:astro_brain/features/alignment/alignment_bloc.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_screen.dart';
import 'package:astro_brain/features/hub/hub_screen.dart';
import 'package:astro_brain/features/hub/widgets/hub_card.dart';
import 'package:astro_brain/features/manual/manual_bloc.dart';
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

// ---------------------------------------------------------------------------
// Helpers JSON pour construire des SystemState de test
// ---------------------------------------------------------------------------

SystemState _systemWithGps(String gpsState) => SystemState.fromJson(
      jsonDecode('''
{
  "overall":"green",
  "subsystems":{
    "mount":{"state":"ready","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "gps":{"state":"$gpsState","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "tracking":{"state":"off","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "network":{"state":"client","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "system":{"state":"ok","details":{},"since":"2026-01-01T00:00:00Z","message":null}
  },
  "seq":1,"ts":"2026-01-01T00:00:00Z"
}
''') as Map<String, dynamic>,
    );

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

Widget _wrap(Widget child, AppBloc bloc, ThemeCubit theme, PiHost host,
    {ApiService? api}) {
  final apiService = api ?? _MockApi();
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>.value(value: host),
      RepositoryProvider<ApiService>.value(value: apiService),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
    ],
    child: MultiBlocProvider(
      providers: [
        BlocProvider<AppBloc>.value(value: bloc),
        BlocProvider<ThemeCubit>.value(value: theme),
        BlocProvider<ManualBloc>(create: (_) => ManualBloc(api: apiService)),
        BlocProvider<AlignmentBloc>(
          create: (_) =>
              AlignmentBloc(repo: AlignmentRepository(api: apiService)),
        ),
        BlocProvider<CatalogueBloc>(
          create: (_) =>
              CatalogueBloc(repo: CatalogueRepository(api: apiService)),
        ),
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

  testWidgets('HubScreen renders 6 cards in order', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    // Verify the first visible cards (onscreen at launch).
    expect(find.text('MANUEL'), findsOneWidget);
    expect(find.text('ALIGNER'), findsOneWidget);
    expect(find.text('CATALOGUE'), findsOneWidget);

    // Scroll to the bottom to verify the remaining cards are present.
    await tester.scrollUntilVisible(find.text('À PROPOS'), 100);
    await tester.pump();

    expect(find.text('SETUP'), findsOneWidget);
    expect(find.text('STATUS'), findsOneWidget);
    expect(find.text('À PROPOS'), findsOneWidget);
  });

  testWidgets('HubScreen first card is primary', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    // At launch the first visible card (MANUEL) is the primary one.
    final cards = tester.widgetList<HubCard>(find.byType(HubCard)).toList();
    expect(cards[0].primary, isTrue);
    for (final c in cards.skip(1)) {
      expect(c.primary, isFalse);
    }
  });

  testWidgets('HubScreen tile ALIGNER is present', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    expect(find.text('ALIGNER'), findsOneWidget);
  });

  testWidgets('HubScreen header shows title and overline', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    expect(find.text('// ASTRO-BRAIN'), findsOneWidget);
    expect(find.text('Que fait-on ce soir ?'), findsOneWidget);
  });

  testWidgets('Tapping MANUEL pushes ManualScreen', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    await tester.tap(find.text('MANUEL'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(ManualScreen), findsOneWidget);
  });

  testWidgets('Tapping SETUP pushes SetupScreen', (tester) async {
    final apiMock = _MockApi();
    when(() => apiMock.getCalibrationStatus(any()))
        .thenAnswer((_) async => throw Exception('not under test'));

    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host, api: apiMock),
    );
    await tester.pump();

    await tester.tap(find.text('SETUP'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(SetupScreen), findsOneWidget);
  });

  testWidgets('Tapping STATUS pushes SystemScreen', (tester) async {
    await tester.pumpWidget(_wrap(const HubScreen(), bloc, theme, host));
    await tester.pump();

    await tester.scrollUntilVisible(find.text('STATUS'), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.pump();
    await tester.tap(find.text('STATUS'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(SystemScreen), findsOneWidget);
  });

  testWidgets('Tapping À PROPOS pushes AboutScreen', (tester) async {
    final apiMock = _MockApi();
    when(() => apiMock.getAbout())
        .thenAnswer((_) async => throw Exception('not under test'));

    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host, api: apiMock),
    );
    await tester.pump();

    await tester.scrollUntilVisible(find.text('À PROPOS'), 100);
    await tester.pump();

    await tester.tap(find.text('À PROPOS'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(AboutScreen), findsOneWidget);
  });

  testWidgets('CATALOGUE card navigates to CatalogueScreen', (tester) async {
    final apiMock = _MockApi();
    when(() => apiMock.getJson(any())).thenAnswer(
      (_) async => {'objects': [], 'count': 0, 'limit': 500, 'offset': 0},
    );

    await tester.pumpWidget(
      _wrap(const HubScreen(), bloc, theme, host, api: apiMock),
    );
    await tester.pump();

    await tester.tap(find.text('CATALOGUE'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(CatalogueScreen), findsOneWidget);
  });

  // ---------------------------------------------------------------------------
  // Précondition GPS Hub — bandeau « Position GPS requise »
  // ---------------------------------------------------------------------------

  testWidgets(
    'ALIGNER — aucun bandeau GPS quand le GPS Pi a un fix3d',
    (tester) async {
      // Crée un bloc dont le stream émet immédiatement un état avec fix3d.
      final controller = StreamController<SystemState>.broadcast();
      final localStream = _MockStream();
      when(() => localStream.stream).thenAnswer((_) => controller.stream);
      when(() => localStream.start()).thenAnswer((_) {
        controller.add(_systemWithGps('fix_3d'));
      });
      when(() => localStream.stop()).thenAnswer((_) async {});
      when(() => localStream.dispose()).thenAnswer((_) async {});

      final localBloc = AppBloc(eventStream: localStream)
        ..add(const AppStarted());

      addTearDown(() async {
        await localBloc.close();
        await controller.close();
      });

      await tester.pumpWidget(_wrap(const HubScreen(), localBloc, theme, host));
      await tester.pump(); // process AppStarted → state with gps
      await tester.pump(); // rebuild HubScreen with new state

      expect(find.text('Position GPS requise'), findsNothing);
    },
  );

  testWidgets(
    'ALIGNER — bandeau GPS affiché quand le GPS Pi est en no_fix',
    (tester) async {
      final controller = StreamController<SystemState>.broadcast();
      final localStream = _MockStream();
      when(() => localStream.stream).thenAnswer((_) => controller.stream);
      when(() => localStream.start()).thenAnswer((_) {
        controller.add(_systemWithGps('no_fix'));
      });
      when(() => localStream.stop()).thenAnswer((_) async {});
      when(() => localStream.dispose()).thenAnswer((_) async {});

      final localBloc = AppBloc(eventStream: localStream)
        ..add(const AppStarted());

      addTearDown(() async {
        await localBloc.close();
        await controller.close();
      });

      await tester.pumpWidget(_wrap(const HubScreen(), localBloc, theme, host));
      await tester.pump(); // process AppStarted → state with gps
      await tester.pump(); // rebuild HubScreen with new state

      expect(find.textContaining('Position GPS requise'), findsOneWidget);
    },
  );
}
