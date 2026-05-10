import 'package:equatable/equatable.dart';

import 'alignment_models.dart';

/// États du wizard d'alignement 3 étoiles.
sealed class AlignmentState extends Equatable {
  const AlignmentState();
  @override
  List<Object?> get props => const [];
}

class AlignmentIdle extends AlignmentState {
  const AlignmentIdle();
}

class AlignmentLoadingCandidates extends AlignmentState {
  const AlignmentLoadingCandidates();
}

class AlignmentPrePointing extends AlignmentState {
  const AlignmentPrePointing({required this.session});
  final AlignmentSessionDto session;
  @override
  List<Object?> get props => [session];
}

class AlignmentFineTuning extends AlignmentState {
  const AlignmentFineTuning({required this.session});
  final AlignmentSessionDto session;
  @override
  List<Object?> get props => [session];
}

class AlignmentValidating extends AlignmentState {
  const AlignmentValidating({required this.model, required this.candidates});
  final AlignmentModelDto model;
  final List<StarDto> candidates;
  @override
  List<Object?> get props => [model, candidates];
}

class AlignmentDone extends AlignmentState {
  const AlignmentDone();
}

class AlignmentError extends AlignmentState {
  const AlignmentError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}
