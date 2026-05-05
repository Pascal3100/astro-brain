/// BLoC gérant la calibration ADXL345 « niveau monture ».
///
/// Cycle de vie :
///   idle → (Started) POST /start → ouverture stream SSE → sampling
///   sampling → (Progress*) state.progress mis à jour
///   sampling → (FinalizeRequested) computing → POST /finalize → done
///   sampling → (AbortRequested) → POST /abort → aborted
///   * → erreur HTTP/SSE → error
///
/// Le bloc ne possède pas le service stream : il reçoit une factory
/// `progressStream` injectable pour tester (cf. README task A-11).
library;

import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/calibration.dart';
import '../../../services/api_service.dart';
import 'adxl_mount_event.dart';
import 'adxl_mount_state.dart';

const String _sensorId = 'adxl345_mount';

class AdxlMountBloc extends Bloc<AdxlMountEvent, AdxlMountState> {
  AdxlMountBloc({
    required ApiService api,
    required Stream<CalibrationProgress> Function(String sessionId)
    progressStream,
  }) : _api = api,
       _progressStream = progressStream,
       super(const AdxlMountState()) {
    on<AdxlMountStarted>(_onStarted);
    on<AdxlMountProgressReceived>(_onProgress);
    on<AdxlMountSseEnded>(_onSseEnded);
    on<AdxlMountSseError>(_onSseError);
    on<AdxlMountFinalizeRequested>(_onFinalize);
    on<AdxlMountAbortRequested>(_onAbort);
  }

  final ApiService _api;
  final Stream<CalibrationProgress> Function(String sessionId) _progressStream;
  StreamSubscription<CalibrationProgress>? _sseSub;

  Future<void> _onStarted(
    AdxlMountStarted event,
    Emitter<AdxlMountState> emit,
  ) async {
    if (state.status == AdxlMountStatus.sampling ||
        state.status == AdxlMountStatus.computing) {
      return;
    }
    emit(const AdxlMountState(status: AdxlMountStatus.idle));
    try {
      final sessionId = await _api.startCalibration(_sensorId);
      emit(
        state.copyWith(
          status: AdxlMountStatus.sampling,
          progress: null,
          errorMessage: null,
        ),
      );
      await _sseSub?.cancel();
      _sseSub = _progressStream(sessionId).listen(
        (p) => add(AdxlMountProgressReceived(p)),
        onError: (Object e) => add(AdxlMountSseError(e.toString())),
        onDone: () => add(const AdxlMountSseEnded()),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlMountStatus.error,
          errorMessage: e.toString(),
        ),
      );
    }
  }

  void _onProgress(
    AdxlMountProgressReceived event,
    Emitter<AdxlMountState> emit,
  ) {
    if (state.status != AdxlMountStatus.sampling) return;
    emit(state.copyWith(progress: event.payload));
  }

  void _onSseEnded(AdxlMountSseEnded event, Emitter<AdxlMountState> emit) {
    // Le stream se ferme naturellement après finalize/abort (`done`,
    // `aborted`, `error`) — on n'a rien à faire dans ces cas. Si on est
    // toujours en `sampling`, c'est anormal (déconnexion réseau, backend
    // crash) : on bascule en error et l'utilisateur peut redémarrer.
    if (state.status == AdxlMountStatus.sampling) {
      emit(
        state.copyWith(
          status: AdxlMountStatus.error,
          errorMessage: 'Stream SSE interrompu',
        ),
      );
    }
  }

  void _onSseError(AdxlMountSseError event, Emitter<AdxlMountState> emit) {
    if (state.status == AdxlMountStatus.sampling) {
      emit(
        state.copyWith(
          status: AdxlMountStatus.error,
          errorMessage: event.message,
        ),
      );
    }
  }

  Future<void> _onFinalize(
    AdxlMountFinalizeRequested event,
    Emitter<AdxlMountState> emit,
  ) async {
    if (state.status != AdxlMountStatus.sampling) return;
    emit(state.copyWith(status: AdxlMountStatus.computing));
    try {
      final status = await _api.finalizeCalibration(_sensorId);
      emit(
        state.copyWith(status: AdxlMountStatus.done, finalizedStatus: status),
      );
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlMountStatus.error,
          errorMessage: e.toString(),
        ),
      );
    }
  }

  Future<void> _onAbort(
    AdxlMountAbortRequested event,
    Emitter<AdxlMountState> emit,
  ) async {
    try {
      await _api.abortCalibration(_sensorId);
      emit(state.copyWith(status: AdxlMountStatus.aborted, errorMessage: null));
    } catch (e) {
      emit(
        state.copyWith(
          status: AdxlMountStatus.error,
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
