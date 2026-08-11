import 'package:astro_brain/features/splash/splash_cubit.dart';
import 'package:astro_brain/features/splash/splash_screen.dart';
import 'package:astro_brain/features/splash/splash_state.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockSplashCubit extends MockCubit<SplashState> implements SplashCubit {}

ThemeData _theme() => ThemeData(
      extensions: <ThemeExtension<dynamic>>[
        AppColors.day,
        const AppTextStyles(
          hudLabel: TextStyle(),
          hudValue: TextStyle(),
          hudCaption: TextStyle(),
          hudBadge: TextStyle(),
        ),
      ],
    );

Widget _host(SplashCubit cubit) => MaterialApp(
      theme: _theme(),
      home: BlocProvider<SplashCubit>.value(
        value: cubit,
        child: SplashScreen(onReady: () {}),
      ),
    );

void main() {
  group('stepStatusFor', () {
    test('nominal : étape courante active, suivantes en attente', () {
      const s = SplashState(phase: SplashPhase.contacting);
      expect(stepStatusFor(s, SplashPhase.contacting), SplashStepState.active);
      expect(stepStatusFor(s, SplashPhase.loading), SplashStepState.pending);
      expect(stepStatusFor(s, SplashPhase.openingStream), SplashStepState.pending);
    });

    test('succès : toutes les étapes faites', () {
      const s = SplashState(phase: SplashPhase.success);
      expect(stepStatusFor(s, SplashPhase.contacting), SplashStepState.done);
      expect(stepStatusFor(s, SplashPhase.loading), SplashStepState.done);
      expect(stepStatusFor(s, SplashPhase.openingStream), SplashStepState.done);
    });
  });

  group('SplashScreen — boot', () {
    testWidgets('affiche les étapes de boot, sans page-barrage d\'erreur',
        (tester) async {
      final cubit = _MockSplashCubit();
      when(() => cubit.start()).thenAnswer((_) async {});
      whenListen(
        cubit,
        const Stream<SplashState>.empty(),
        initialState: const SplashState(phase: SplashPhase.contacting),
      );

      await tester.pumpWidget(_host(cubit));
      await tester.pump();

      expect(find.text('CONTACTING ASTRO-BRAIN.LOCAL'), findsOneWidget);
      // Plus de page d'erreur ni d'affordances dupliquées avec l'AppBar du Hub.
      expect(find.text('ASTRO-BRAIN NOT REACHABLE'), findsNothing);
      expect(find.byKey(const Key('splash-retry')), findsNothing);
      expect(find.byKey(const Key('splash-configure-network')), findsNothing);
    });
  });
}
