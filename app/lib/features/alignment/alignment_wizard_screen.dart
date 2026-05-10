import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'alignment_bloc.dart';
import 'alignment_event.dart';
import 'alignment_state.dart';
import 'screens/done_screen.dart';
import 'screens/intro_screen.dart';
import 'screens/per_star_screen.dart';
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
          // TODO(macro-3-runtime): brancher coords mount + cible (T21)
          return PerStarScreen(
            stepIndex: session.currentIdx + 1,
            totalSteps: 3,
            target: session.candidates[session.currentIdx],
            targetAz: 0.0,
            targetAlt: 0.0,
            currentAz: 0.0,
            currentAlt: 0.0,
            rate: 4,
            onPress: (_) {},
            onRelease: () {},
            onRateChanged: (_) {},
            onCentered: () => bloc.add(RecordRequested(session.currentIdx)),
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
}
