import 'package:astro_brain/features/setup/network/network_screen.dart';
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

void main() {
  late SharedPreferences prefs;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
  });

  testWidgets('renders host, port fields and three buttons', (tester) async {
    await tester.pumpWidget(
      MultiRepositoryProvider(
        providers: [
          RepositoryProvider<PiHost>(create: (_) => const PiHost()),
          RepositoryProvider<ApiService>(create: (_) => _MockApi()),
          RepositoryProvider<EventStreamService>(
            create: (_) {
              final s = _MockStream();
              when(() => s.stream)
                  .thenAnswer((_) => const Stream<SystemState>.empty());
              when(() => s.start()).thenAnswer((_) {});
              when(() => s.stop()).thenAnswer((_) async {});
              when(() => s.dispose()).thenAnswer((_) async {});
              return s;
            },
          ),
          RepositoryProvider<SharedPreferences>.value(value: prefs),
        ],
        child: MultiBlocProvider(
          providers: [
            BlocProvider<AppBloc>(
              create: (ctx) =>
                  AppBloc(eventStream: ctx.read<EventStreamService>()),
            ),
            BlocProvider<ThemeCubit>(
              create: (_) => ThemeCubit(prefs: prefs),
            ),
          ],
          child: MaterialApp(
            theme: _testTheme(),
            home: const NetworkScreen(),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('TESTER'), findsOneWidget);
    expect(find.text('ENREGISTRER'), findsOneWidget);
    expect(find.text('RÉINITIALISER'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
  });
}
