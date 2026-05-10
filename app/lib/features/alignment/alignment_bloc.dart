import 'package:flutter_bloc/flutter_bloc.dart';

import 'alignment_event.dart';
import 'alignment_repository.dart';
import 'alignment_state.dart';

/// Orchestrateur du wizard d'alignement 3 étoiles.
class AlignmentBloc extends Bloc<AlignmentEvent, AlignmentState> {
  AlignmentBloc({required this.repo}) : super(const AlignmentIdle()) {
    on<WizardStarted>(_onStarted);
    on<RecordRequested>(_onRecord);
    on<RestartStarRequested>(_onRestart);
    on<ValidationAccepted>((e, emit) => emit(const AlignmentDone()));
    on<WizardCancelled>(_onCancel);
    on<StarSwapRequested>(_onSwap);
    on<PrePointingDone>((e, emit) {
      final s = state;
      if (s is AlignmentPrePointing) {
        emit(AlignmentFineTuning(session: s.session));
      }
    });
    on<MountDisconnected>(
      (e, emit) => emit(const AlignmentError('Monture déconnectée')),
    );
  }

  final AlignmentRepository repo;

  Future<void> _onStarted(
      WizardStarted e, Emitter<AlignmentState> emit) async {
    emit(const AlignmentLoadingCandidates());
    try {
      final existing = await repo.getSession();
      final session = existing ?? await repo.start();
      emit(AlignmentPrePointing(session: session));
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onRecord(
      RecordRequested e, Emitter<AlignmentState> emit) async {
    try {
      final updated = await repo.record(e.idx);
      if (updated.recordedStars.length >= 3) {
        final model = await repo.finalize();
        emit(AlignmentValidating(model: model));
      } else {
        emit(AlignmentPrePointing(session: updated));
      }
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onRestart(
      RestartStarRequested e, Emitter<AlignmentState> emit) async {
    try {
      final s = await repo.restartStar(e.idx);
      emit(AlignmentPrePointing(session: s));
    } catch (err) {
      emit(AlignmentError(err.toString()));
    }
  }

  Future<void> _onCancel(
      WizardCancelled e, Emitter<AlignmentState> emit) async {
    try {
      await repo.cancel();
    } catch (_) {
      // Annulation best-effort : on retombe sur Idle même en cas d'erreur.
    }
    emit(const AlignmentIdle());
  }

  Future<void> _onSwap(
      StarSwapRequested e, Emitter<AlignmentState> emit) async {
    // L'écran Intro pop un dialog avec un sélecteur ; quand un star est choisi,
    // ce dialog appelle directement repo.swap() puis re-dispatche.
    // Ici on est juste passe-plat pour l'idx demandé.
  }
}
