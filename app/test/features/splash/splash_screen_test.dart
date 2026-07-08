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

    test(
        'échec en contacting : aucune étape « faite », contacting en erreur '
        '(régression du bug d\'affichage tout-vert)', () {
      const s = SplashState(
        phase: SplashPhase.failure,
        failedPhase: SplashPhase.contacting,
      );
      expect(stepStatusFor(s, SplashPhase.contacting), SplashStepState.error);
      expect(stepStatusFor(s, SplashPhase.loading), SplashStepState.pending);
      expect(stepStatusFor(s, SplashPhase.openingStream), SplashStepState.pending);
    });

    test('échec tardif : étapes franchies faites, celle en échec en erreur', () {
      const s = SplashState(
        phase: SplashPhase.failure,
        failedPhase: SplashPhase.openingStream,
      );
      expect(stepStatusFor(s, SplashPhase.contacting), SplashStepState.done);
      expect(stepStatusFor(s, SplashPhase.loading), SplashStepState.done);
      expect(stepStatusFor(s, SplashPhase.openingStream), SplashStepState.error);
    });
  });

  group('SplashScreen — écran d\'échec', () {
    testWidgets('affiche RETRY, CONFIGURER LE RÉSEAU et le message d\'erreur',
        (tester) async {
      final cubit = _MockSplashCubit();
      when(() => cubit.start()).thenAnswer((_) async {});
      whenListen(
        cubit,
        const Stream<SplashState>.empty(),
        initialState: const SplashState(
          phase: SplashPhase.failure,
          errorMessage: 'boom',
          failedPhase: SplashPhase.contacting,
        ),
      );

      await tester.pumpWidget(_host(cubit));
      await tester.pump();

      expect(find.text('ASTRO-BRAIN NOT REACHABLE'), findsOneWidget);
      expect(find.byKey(const Key('splash-retry')), findsOneWidget);
      expect(find.byKey(const Key('splash-configure-network')), findsOneWidget);
    });

    testWidgets('RETRY relance le cubit', (tester) async {
      final cubit = _MockSplashCubit();
      when(() => cubit.start()).thenAnswer((_) async {});
      whenListen(
        cubit,
        const Stream<SplashState>.empty(),
        initialState: const SplashState(
          phase: SplashPhase.failure,
          errorMessage: 'boom',
          failedPhase: SplashPhase.contacting,
        ),
      );

      await tester.pumpWidget(_host(cubit));
      await tester.pump();
      await tester.tap(find.byKey(const Key('splash-retry')));

      // start() est appelé une fois au montage (postFrame) + une fois au tap.
      verify(() => cubit.start()).called(greaterThanOrEqualTo(1));
    });
  });
}
