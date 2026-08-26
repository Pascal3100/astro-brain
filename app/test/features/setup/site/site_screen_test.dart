import 'package:astro_brain/features/setup/site/site_bloc.dart';
import 'package:astro_brain/features/setup/site/site_event.dart';
import 'package:astro_brain/features/setup/site/site_repository.dart';
import 'package:astro_brain/features/setup/site/site_screen.dart';
import 'package:astro_brain/features/setup/site/site_state.dart';
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

/// Mock du bloc : la vue est testée seule, sans jamais lancer d'IO réelle
/// (un vrai `SiteBloc` irait chercher le GPS du téléphone au tap).
class _MockSiteBloc extends Mock implements SiteBloc {}

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

void main() {
  late SharedPreferences prefs;
  late _MockSiteBloc bloc;

  setUpAll(() {
    registerFallbackValue(const SiteLoaded());
  });

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    bloc = _MockSiteBloc();
    when(() => bloc.stream).thenAnswer((_) => const Stream<SiteState>.empty());
    when(() => bloc.close()).thenAnswer((_) async {});
  });

  Widget wrap() {
    final stream = _MockStream();
    when(() => stream.stream)
        .thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => stream.start()).thenAnswer((_) {});
    when(() => stream.stop()).thenAnswer((_) async {});
    when(() => stream.dispose()).thenAnswer((_) async {});

    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider<PiHost>(create: (_) => const PiHost()),
        RepositoryProvider<ApiService>(create: (_) => _MockApi()),
        RepositoryProvider<EventStreamService>.value(value: stream),
        RepositoryProvider<SharedPreferences>.value(value: prefs),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider<AppBloc>(
            create: (ctx) =>
                AppBloc(eventStream: ctx.read<EventStreamService>()),
          ),
          BlocProvider<ThemeCubit>(create: (_) => ThemeCubit(prefs: prefs)),
          BlocProvider<SiteBloc>.value(value: bloc),
        ],
        child: MaterialApp(
          theme: _testTheme(),
          home: const SiteView(),
        ),
      ),
    );
  }

  testWidgets('site connu — affiche latitude, longitude et date de réglage',
      (tester) async {
    when(() => bloc.state).thenReturn(
      SiteState(
        status: SiteStatus.ready,
        site: ObservingSite(
          lat: 43.6045,
          lon: 1.4442,
          setAt: DateTime.utc(2026, 8, 26, 20),
        ),
      ),
    );

    await tester.pumpWidget(wrap());
    await tester.pump();

    expect(find.text('43.60450°'), findsOneWidget);
    expect(find.text('1.44420°'), findsOneWidget);
    expect(find.text('SITE DÉFINI'), findsOneWidget);
  });

  testWidgets('aucun site — état vide explicite, pas une erreur',
      (tester) async {
    when(() => bloc.state)
        .thenReturn(const SiteState(status: SiteStatus.ready));

    await tester.pumpWidget(wrap());
    await tester.pump();

    expect(find.text('AUCUN SITE'), findsOneWidget);
    expect(find.text('NON DÉFINI'), findsOneWidget);
  });

  testWidgets('tap sur le bouton émet SiteFromPhoneRequested',
      (tester) async {
    when(() => bloc.state)
        .thenReturn(const SiteState(status: SiteStatus.ready));
    when(() => bloc.add(any())).thenReturn(null);

    await tester.pumpWidget(wrap());
    await tester.pump();

    await tester.tap(find.text('UTILISER LA POSITION DU TÉLÉPHONE'));
    await tester.pump();

    verify(() => bloc.add(const SiteFromPhoneRequested())).called(1);
  });

  testWidgets('acquisition en cours — bouton désactivé', (tester) async {
    when(() => bloc.state)
        .thenReturn(const SiteState(status: SiteStatus.saving));

    await tester.pumpWidget(wrap());
    await tester.pump();

    expect(find.text('ACQUISITION GPS…'), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
  });

  testWidgets('erreur — le message est affiché dans la ligne de statut',
      (tester) async {
    when(() => bloc.state).thenReturn(
      const SiteState(status: SiteStatus.error, error: 'permission refusée'),
    );

    await tester.pumpWidget(wrap());
    await tester.pump();

    expect(find.textContaining('permission refusée'), findsOneWidget);
  });
}
