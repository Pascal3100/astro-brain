import 'package:equatable/equatable.dart';

import 'alignment_models.dart';

/// Événements du wizard d'alignement 3 étoiles.
sealed class AlignmentEvent extends Equatable {
  const AlignmentEvent();
  @override
  List<Object?> get props => const [];
}

class WizardStarted extends AlignmentEvent {
  const WizardStarted();
}

class CandidatesReceived extends AlignmentEvent {
  const CandidatesReceived();
}

class StarSwapRequested extends AlignmentEvent {
  const StarSwapRequested(this.idx, this.star);
  final int idx;
  final StarDto star;
  @override
  List<Object?> get props => [idx, star];
}

class PrePointingDone extends AlignmentEvent {
  const PrePointingDone();
}

class RecordRequested extends AlignmentEvent {
  const RecordRequested(this.idx);
  final int idx;
  @override
  List<Object?> get props => [idx];
}

class ValidationAccepted extends AlignmentEvent {
  const ValidationAccepted();
}

class RestartStarRequested extends AlignmentEvent {
  const RestartStarRequested(this.idx);
  final int idx;
  @override
  List<Object?> get props => [idx];
}

class WizardCancelled extends AlignmentEvent {
  const WizardCancelled();
}

class MountDisconnected extends AlignmentEvent {
  const MountDisconnected();
}
