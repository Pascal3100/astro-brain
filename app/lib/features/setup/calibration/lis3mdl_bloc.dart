/// BLoC gérant la calibration LIS3MDL « compass ».
///
/// Cycle de vie :
///   idle → (Started) POST /start → ouverture stream SSE → sampling
///   sampling → (Progress*) state.progress mis à jour
///   sampling → (FinalizeRequested) computing → POST /finalize → done
///   sampling → (AbortRequested) → POST /abort → aborted
///   * → erreur HTTP/SSE → error
///
/// Mirror exact d'`AdxlMountBloc` (cf. task A-12) : à 2 implémentations,
/// l'abstraction est prématurée. Re-évaluer après A-13.
library;

import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/calibration.dart';
import '../../../services/api_service.dart';
import 'lis3mdl_event.dart';
import 'lis3mdl_state.dart';

const String _sensorId = 'lis3mdl';

class Lis3mdlBloc extends Bloc<Lis3mdlEvent, Lis3mdlState> {
  Lis3mdlBloc({
    required ApiService api,
    required Stream<CalibrationProgress> Function(String sessionId)
    progressStream,
  }) : _api = api,
       _progressStream = progressStream,
       super(const Lis3mdlState()) {
    on<Lis3mdlStarted>(_onStarted);
    on<Lis3mdlProgressReceived>(_onProgress);
    on<Lis3mdlSseEnded>(_onSseEnded);
    on<Lis3mdlSseError>(_onSseError);
    on<Lis3mdlFinalizeRequested>(_onFinalize);
    on<Lis3mdlAbortRequested>(_onAbort);
  }

  final ApiService _api;
  final Stream<CalibrationProgress> Function(String sessionId) _progressStream;
  StreamSubscription<CalibrationProgress>? _sseSub;

  Future<void> _onStarted(
    Lis3mdlStarted event,
    Emitter<Lis3mdlState> emit,
  ) async {
    if (state.status == Lis3mdlStatus.sampling ||
        state.status == Lis3mdlStatus.computing) {
      return;
    }
    emit(const Lis3mdlState(status: Lis3mdlStatus.idle));
    try {
      final sessionId = await _api.startCalibration(_sensorId);
      emit(
        state.copyWith(
          status: Lis3mdlStatus.sampling,
          progress: null,
          errorMessage: null,
        ),
      );
      await _sseSub?.cancel();
      _sseSub = _progressStream(sessionId).listen(
        (p) => add(Lis3mdlProgressReceived(p)),
        onError: (Object e) => add(Lis3mdlSseError(e.toString())),
        onDone: () => add(const Lis3mdlSseEnded()),
      );
    } catch (e) {
      emit(
        state.copyWith(status: Lis3mdlStatus.error, errorMessage: e.toString()),
      );
    }
  }

  void _onProgress(Lis3mdlProgressReceived event, Emitter<Lis3mdlState> emit) {
    if (state.status != Lis3mdlStatus.sampling) return;
    emit(state.copyWith(progress: event.payload));
  }

  void _onSseEnded(Lis3mdlSseEnded event, Emitter<Lis3mdlState> emit) {
    // Le stream se ferme naturellement après finalize/abort (`done`,
    // `aborted`, `error`) — on n'a rien à faire dans ces cas. Si on est
    // toujours en `sampling`, c'est anormal (déconnexion réseau, backend
    // crash) : on bascule en error et l'utilisateur peut redémarrer.
    if (state.status == Lis3mdlStatus.sampling) {
      emit(
        state.copyWith(
          status: Lis3mdlStatus.error,
          errorMessage: 'Stream SSE interrompu',
        ),
      );
    }
  }

  void _onSseError(Lis3mdlSseError event, Emitter<Lis3mdlState> emit) {
    if (state.status == Lis3mdlStatus.sampling) {
      emit(
        state.copyWith(
          status: Lis3mdlStatus.error,
          errorMessage: event.message,
        ),
      );
    }
  }

  Future<void> _onFinalize(
    Lis3mdlFinalizeRequested event,
    Emitter<Lis3mdlState> emit,
  ) async {
    if (state.status != Lis3mdlStatus.sampling) return;
    emit(state.copyWith(status: Lis3mdlStatus.computing));
    try {
      final status = await _api.finalizeCalibration(_sensorId);
      emit(state.copyWith(status: Lis3mdlStatus.done, finalizedStatus: status));
    } catch (e) {
      emit(
        state.copyWith(status: Lis3mdlStatus.error, errorMessage: e.toString()),
      );
    }
  }

  Future<void> _onAbort(
    Lis3mdlAbortRequested event,
    Emitter<Lis3mdlState> emit,
  ) async {
    try {
      await _api.abortCalibration(_sensorId);
      emit(state.copyWith(status: Lis3mdlStatus.aborted, errorMessage: null));
    } catch (e) {
      emit(
        state.copyWith(status: Lis3mdlStatus.error, errorMessage: e.toString()),
      );
    }
  }

  @override
  Future<void> close() async {
    await _sseSub?.cancel();
    _sseSub = null;
    return super.close();
  }
}
