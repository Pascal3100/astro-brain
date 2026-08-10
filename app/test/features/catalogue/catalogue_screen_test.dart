import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_screen.dart';
import 'package:astro_brain/features/setup/reference/reference_models.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
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

class _MockRepo extends Mock implements CatalogueRepository {}

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
  AppBloc appBloc,
  ThemeCubit theme,
  PiHost host,
  CatalogueBloc catalogueBloc, {
  ReferenceRepository? refRepo,
}) {
  return MultiRepositoryProvider(
    providers: [
      RepositoryProvider<PiHost>.value(value: host),
      RepositoryProvider<ApiService>.value(value: _MockApi()),
      RepositoryProvider<EventStreamService>(create: (_) => _MockStream()),
      RepositoryProvider<ReferenceRepository>.value(
        value: refRepo ?? _MockRefRepo(),
      ),
    ],
    child: MultiBlocProvider(
      providers: [
        BlocProvider<AppBloc>.value(value: appBloc),
        BlocProvider<ThemeCubit>.value(value: theme),
        BlocProvider<CatalogueBloc>.value(value: catalogueBloc),
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
  late _MockRepo mockRepo;
  late CatalogueBloc catalogueBloc;
  late _MockRefRepo refRepo;

  setUpAll(() {
    registerFallbackValue('');
  });

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
    when(
      () => mockRepo.listObjects(
        search: any(named: 'search'),
        maxMag: any(named: 'maxMag'),
        visibleNow: any(named: 'visibleNow'),
        kind: any(named: 'kind'),
        messier: any(named: 'messier'),
      ),
    ).thenAnswer((_) async => <CatalogObjectDto>[]);

    catalogueBloc = CatalogueBloc(repo: mockRepo);

    refRepo = _MockRefRepo();
    // Almanach prêt par défaut → bannière masquée, pas d'effet sur ce test.
    when(() => refRepo.getStatus())
        .thenAnswer((_) async => const ReferenceStatusDto(ready: true));
  });

  tearDown(() {
    appBloc.close();
    theme.close();
    catalogueBloc.close();
  });

  testWidgets(
    'shows "non alignée" banner when AppBloc has no system state',
    (tester) async {
      // AppBloc initial state has system == null → isAligned == false.
      await tester.pumpWidget(
        _wrap(
          const CatalogueScreen(),
          appBloc,
          theme,
          host,
          catalogueBloc,
          refRepo: refRepo,
        ),
      );
      await tester.pump();

      expect(find.textContaining('non alignée'), findsOneWidget);
    },
  );
}
