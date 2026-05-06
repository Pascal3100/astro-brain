/// BLoC gérant la calibration ADXL345 « zéro ALT » (capteur tube).
///
/// Cycle de vie :
///   idle → (Started) POST /start → ouverture stream SSE → sampling
///   sampling → (Progress*) state.progress mis à jour
///   sampling → (FinalizeRequested) computing → POST /finalize → done
///   sampling → (AbortRequested) → POST /abort → aborted
///   * → erreur HTTP/SSE → error
///
/// Mirror exact d'`AdxlMountBloc` / `Lis3mdlBloc` : à 3 implémentations
/// l'abstraction commence à se justifier, mais on garde le mirror pour
/// fermer Slice A. Refactor à faire en suivi (cf. backlog).
library;

import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/calibration.dart';
import '../../../services/api_service.dart';
import 'adxl_tube_event.dart';
import 'adxl_tube_state.dart';

const String _sensorId = 'adxl345_tube';

class AdxlTubeBloc extends Bloc<AdxlTubeEvent, AdxlTubeState> {
  AdxlTubeBloc({
    required ApiService api,
    required Stream<CalibrationProgress> Function(String sessionId)
    progressStream,
  }) : _api = api,
       _progressStream = progressStream,
       super(const AdxlTubeState()) {
    on<AdxlTubeStarted>(_onStarted);
    on<AdxlTubeProgressReceived>(_onProgress);
    on<AdxlTubeSseEnded>(_onSseEnded);
    on<AdxlTubeSseError>(_onSseError);
    on<AdxlTubeFinalizeRequested>(_onFinalize);
    on<AdxlTubeAbortRequested>(_onAbort);
  }

  final ApiService _api;
  final Stream<CalibrationProgress> Function(String sessionId) _progressStream;
  StreamSubscription<CalibrationProgress>? _sseSub;

  Future<void> _onStarted(
    AdxlTubeStarted event,
    Emitter<AdxlTubeState> emit,
  ) async {
    if (state.status == AdxlTubeStatus.sampling ||
        state.status == AdxlTubeStatus.computing) {
      return;
    }
    emit(const AdxlTubeState(status: AdxlTubeStatus.idle));
    try {
      final sessionId = await _api.startCalibration(_sensorId);
      emit(
        state.copyWith(
          status: AdxlTubeStatus.sampling,
          progress: null,
          errorMessage: null,
        ),
      );
      await _sseSub?.cancel();
      _sseSub = _progressStream(sessionId).listen(
        (p) => add(AdxlTubeProgressReceived(p)),
        onError: (Object e) => add(AdxlTubeSseError(e.toString())),
        onDone: () => add(const AdxlTubeSseEnded()),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlTubeStatus.error,
          errorMessage: e.toString(),
        ),
      );
    }
  }

  void _onProgress(
    AdxlTubeProgressReceived event,
    Emitter<AdxlTubeState> emit,
  ) {
    if (state.status != AdxlTubeStatus.sampling) return;
    emit(state.copyWith(progress: event.payload));
  }

  void _onSseEnded(AdxlTubeSseEnded event, Emitter<AdxlTubeState> emit) {
    if (state.status == AdxlTubeStatus.sampling) {
      emit(
        state.copyWith(
          status: AdxlTubeStatus.error,
          errorMessage: 'Stream SSE interrompu',
        ),
      );
    }
  }

  void _onSseError(AdxlTubeSseError event, Emitter<AdxlTubeState> emit) {
    if (state.status == AdxlTubeStatus.sampling) {
      emit(
        state.copyWith(
          status: AdxlTubeStatus.error,
          errorMessage: event.message,
        ),
      );
    }
  }

  Future<void> _onFinalize(
    AdxlTubeFinalizeRequested event,
    Emitter<AdxlTubeState> emit,
  ) async {
    if (state.status != AdxlTubeStatus.sampling) return;
    emit(state.copyWith(status: AdxlTubeStatus.computing));
    try {
      final status = await _api.finalizeCalibration(_sensorId);
      emit(
        state.copyWith(status: AdxlTubeStatus.done, finalizedStatus: status),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlTubeStatus.error,
          errorMessage: e.toString(),
        ),
      );
    }
  }

  Future<void> _onAbort(
    AdxlTubeAbortRequested event,
    Emitter<AdxlTubeState> emit,
  ) async {
    try {
      await _api.abortCalibration(_sensorId);
      emit(state.copyWith(status: AdxlTubeStatus.aborted, errorMessage: null));
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlTubeStatus.error,
          errorMessage: e.toString(),
        ),
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
