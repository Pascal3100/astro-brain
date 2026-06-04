import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

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
          // TODO(macro-3-runtime): brancher coords mount + cible (T21)
          return PerStarScreen(
            repo: bloc.repo,
            stepIndex: idx + 1,
            totalSteps: 3,
            target: session.candidates[idx],
            targetAz: 0.0,
            targetAlt: 0.0,
            currentAz: 0.0,
            currentAlt: 0.0,
            rate: 4,
            onPress: (_) {},
            onRelease: () {},
            onRateChanged: (_) {},
            onCentered: () => bloc.add(RecordRequested(idx)),
            onSwapRequested: () => _openStarNavigator(context, bloc, idx),
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
          return Scaffold(body: Center(child: Text(state.message)));
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
          onSelected: (StarDto star) async {
            Navigator.of(context).pop();
            try {
              await bloc.repo.swap(idx, star);
            } on Exception catch (e) {
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Swap échoué : $e')),
                );
                return;
              }
            }
            if (context.mounted) {
              bloc.add(const WizardStarted());
            }
          },
        ),
      ),
    );
  }
}
