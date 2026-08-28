import 'package:flutter/material.dart' hide Axis;
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../widgets/dpad_control.dart';
import '../manual/manual_bloc.dart';
import 'alignment_bloc.dart';
import 'alignment_event.dart';
import 'alignment_models.dart';
import 'alignment_state.dart';
import 'screens/done_screen.dart';
import 'screens/intro_screen.dart';
import 'screens/per_star_screen.dart';
import 'screens/star_navigator_screen.dart';
import 'screens/validation_screen.dart';

/// Host du wizard d'alignement : route l'état du BLoC vers les écrans
/// présentationnels (Intro, PerStar, Validation, Done, Error).
class AlignmentWizardScreen extends StatelessWidget {
  const AlignmentWizardScreen({super.key});

  // Même mappage DPadDirection → Axis/Direction que le _DPadHost du mode
  // manuel : le jog du wizard passe par le ManualBloc (rate partagé 1..8,
  // slew/stop par axe).
  static Axis _axisOfDPad(DPadDirection d) =>
      d == DPadDirection.up || d == DPadDirection.down ? Axis.alt : Axis.az;

  static (Axis, Direction) _mapDPad(DPadDirection d) => switch (d) {
        DPadDirection.up => (Axis.alt, Direction.plus),
        DPadDirection.down => (Axis.alt, Direction.minus),
        DPadDirection.left => (Axis.az, Direction.minus),
        DPadDirection.right => (Axis.az, Direction.plus),
      };

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AlignmentBloc, AlignmentState>(
      builder: (context, state) {
        final bloc = context.read<AlignmentBloc>();
        if (state is AlignmentIdle || state is AlignmentLoadingCandidates) {
          return IntroScreen(
            onStart: () => bloc.add(const WizardStarted()),
          );
        }
        if (state is AlignmentPrePointing || state is AlignmentFineTuning) {
          final session = state is AlignmentPrePointing
              ? state.session
              : (state as AlignmentFineTuning).session;
          final idx = session.currentIdx;
          final manual = context.read<ManualBloc>();
          // TODO(macro-3-runtime): brancher coords mount + cible (T21)
          return BlocBuilder<ManualBloc, ManualState>(
            buildWhen: (a, b) => a.rate != b.rate,
            builder: (context, manualState) => PerStarScreen(
              repo: bloc.repo,
              stepIndex: idx + 1,
              totalSteps: 3,
              target: session.candidates[idx],
              targetAz: 0.0,
              targetAlt: 0.0,
              currentAz: 0.0,
              currentAlt: 0.0,
              rate: manualState.rate,
              onPress: (d) {
                final (axis, direction) = _mapDPad(d);
                manual.add(
                  ManualSlewPressed(axis: axis, direction: direction),
                );
              },
              onRelease: (d) =>
                  manual.add(ManualSlewReleased(_axisOfDPad(d))),
              onRateChanged: (v) => manual.add(ManualRateChanged(v)),
              onCentered: () => bloc.add(RecordRequested(idx)),
              onSwapRequested: () => _openStarNavigator(context, bloc, idx),
            ),
          );
        }
        if (state is AlignmentValidating) {
          return ValidationScreen(
            model: state.model,
            candidates: state.candidates,
            onAccept: () => bloc.add(const ValidationAccepted()),
            onRestartStar: (idx) => bloc.add(RestartStarRequested(idx)),
          );
        }
        if (state is AlignmentDone) {
          return const DoneScreen();
        }
        if (state is AlignmentError) {
          // Toujours offrir une sortie : un wizard utilisé de nuit, sur le
          // terrain, ne doit jamais finir sur un cul-de-sac (S58).
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(state.message, textAlign: TextAlign.center),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: () => bloc.add(const WizardStarted()),
                      child: const Text('RECOMMENCER'),
                    ),
                  ],
                ),
              ),
            ),
          );
        }
        return const SizedBox.shrink();
      },
    );
  }

  /// Ouvre le navigateur d'étoiles pour swapper l'étoile à l'index [idx].
  ///
  /// Quand l'utilisateur choisit une étoile, on appelle directement
  /// [repo.swap(idx, star)] (comme indiqué dans le commentaire de
  /// [AlignmentBloc._onSwap]), puis on redémarre le wizard pour recharger
  /// la session mise à jour.
  Future<void> _openStarNavigator(
    BuildContext context,
    AlignmentBloc bloc,
    int idx,
  ) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => StarNavigatorScreen(
          repository: bloc.repo,
          onSelected: (StarDto star) {
            Navigator.of(context).pop();
            bloc.add(StarSwapRequested(idx, star));
          },
        ),
      ),
    );
  }
}
