/// BLoC générique de calibration capteur.
///
/// Cycle de vie pour le capteur compass (`lis3mdl`) :
///   idle → (Started) POST /start → ouverture stream SSE → sampling
///   sampling → (ProgressReceived*) state.progress mis à jour
///   sampling → (FinalizeRequested) computing → POST /finalize → done
///   sampling → (AbortRequested) → POST /abort → aborted
///   * → erreur HTTP/SSE → error
///
/// Ce qui varie entre capteurs : le `sensorId` et la fonction `finalizeGate`
/// qui décide quand le bouton VALIDER s'active. Le seuil est défini dans ce
/// fichier (cf. [lis3mdlCanFinalize]).
///
/// Note : on réutilise l'enum [CalibrationState] du modèle pour la phase
/// du bloc — ses valeurs (`idle/sampling/computing/done/aborted/error`)
/// recouvrent exactement nos besoins. Pour éviter le clash, la classe
/// d'état du bloc s'appelle [CalibrationBlocState].
library;

import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/calibration.dart';
import '../../../services/api_service.dart';

// Réexport pour que les écrans n'aient qu'un seul import à faire pour
// accéder à `CalibrationState` (enum) et `CalibrationStatus` (modèle).
export '../../../models/calibration.dart'
    show CalibrationState, CalibrationStatus, CalibrationProgress;

// -----------------------------------------------------------------------------
// Gates par capteur — miroir des défauts backend (cf. services/calibration.py)
// -----------------------------------------------------------------------------

/// LIS3MDL : `lis3mdl_min_samples=500`, `lis3mdl_coverage_threshold=80.0`.
/// Le backend ne gate pas sur `residual` côté finalize ; on reproduit les
/// deux gates effectives uniquement.
const int kLis3mdlMinSamples = 500;
const double kLis3mdlCoverageThreshold = 80.0;

bool lis3mdlCanFinalize(CalibrationProgress p) =>
    p.samplesN >= kLis3mdlMinSamples &&
    p.coveragePct >= kLis3mdlCoverageThreshold;

// -----------------------------------------------------------------------------
// Events
// -----------------------------------------------------------------------------

abstract class CalibrationEvent extends Equatable {
  const CalibrationEvent();
  @override
  List<Object?> get props => const [];
}

/// Démarre la session : POST /start puis ouvre le stream SSE.
class CalibrationStarted extends CalibrationEvent {
  const CalibrationStarted();
}

/// Un nouvel échantillon de progression est arrivé via SSE.
class CalibrationProgressReceived extends CalibrationEvent {
  const CalibrationProgressReceived(this.payload);
  final CalibrationProgress payload;
  @override
  List<Object?> get props => [payload];
}

/// Le stream SSE s'est terminé naturellement (end event ou connexion close).
class CalibrationSseEnded extends CalibrationEvent {
  const CalibrationSseEnded();
}

/// Erreur transport sur le stream SSE.
class CalibrationSseError extends CalibrationEvent {
  const CalibrationSseError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Bouton VALIDER : POST /finalize.
class CalibrationFinalizeRequested extends CalibrationEvent {
  const CalibrationFinalizeRequested();
}

/// Bouton ANNULER : POST /abort.
class CalibrationAbortRequested extends CalibrationEvent {
  const CalibrationAbortRequested();
}

// -----------------------------------------------------------------------------
// State
// -----------------------------------------------------------------------------

const _sentinel = Object();

class CalibrationBlocState extends Equatable {
  const CalibrationBlocState({
    this.status = CalibrationState.idle,
    this.progress,
    this.errorMessage,
    this.finalizedStatus,
    this.finalizeGate,
  });

  final CalibrationState status;
  final CalibrationProgress? progress;
  final String? errorMessage;
  final CalibrationStatus? finalizedStatus;

  /// Callback injecté par le bloc — appliqué dans [canFinalize] pour
  /// décider du gating du bouton VALIDER. Hors `props` : il ne change
  /// jamais pour un bloc donné, n'a pas d'incidence sur l'égalité.
  final bool Function(CalibrationProgress)? finalizeGate;

  /// Le bouton VALIDER est actif uniquement pendant l'échantillonnage,
  /// quand le gate spécifique au capteur est satisfait.
  bool get canFinalize {
    if (status != CalibrationState.sampling) return false;
    if (progress == null || finalizeGate == null) return false;
    return finalizeGate!(progress!);
  }

  CalibrationBlocState copyWith({
    CalibrationState? status,
    Object? progress = _sentinel,
    Object? errorMessage = _sentinel,
    Object? finalizedStatus = _sentinel,
  }) => CalibrationBlocState(
    status: status ?? this.status,
    progress: identical(progress, _sentinel)
        ? this.progress
        : progress as CalibrationProgress?,
    errorMessage: identical(errorMessage, _sentinel)
        ? this.errorMessage
        : errorMessage as String?,
    finalizedStatus: identical(finalizedStatus, _sentinel)
        ? this.finalizedStatus
        : finalizedStatus as CalibrationStatus?,
    finalizeGate: finalizeGate,
  );

  @override
  List<Object?> get props => [status, progress, errorMessage, finalizedStatus];
}

// -----------------------------------------------------------------------------
// Bloc
// -----------------------------------------------------------------------------

class CalibrationBloc extends Bloc<CalibrationEvent, CalibrationBlocState> {
  CalibrationBloc({
    required ApiService api,
    required String sensorId,
    required bool Function(CalibrationProgress) finalizeGate,
    required Stream<CalibrationProgress> Function(String sessionId)
    progressStream,
  }) : _api = api,
       _sensorId = sensorId,
       _progressStream = progressStream,
       super(CalibrationBlocState(finalizeGate: finalizeGate)) {
    on<CalibrationStarted>(_onStarted);
    on<CalibrationProgressReceived>(_onProgress);
    on<CalibrationSseEnded>(_onSseEnded);
    on<CalibrationSseError>(_onSseError);
    on<CalibrationFinalizeRequested>(_onFinalize);
    on<CalibrationAbortRequested>(_onAbort);
  }

  final ApiService _api;
  final String _sensorId;
  final Stream<CalibrationProgress> Function(String sessionId) _progressStream;
  StreamSubscription<CalibrationProgress>? _sseSub;

  Future<void> _onStarted(
    CalibrationStarted event,
    Emitter<CalibrationBlocState> emit,
  ) async {
    if (state.status == CalibrationState.sampling ||
        state.status == CalibrationState.computing) {
      return;
    }
    emit(state.copyWith(
      status: CalibrationState.idle,
      progress: null,
      errorMessage: null,
      finalizedStatus: null,
    ));
    try {
      final sessionId = await _api.startCalibration(_sensorId);
      emit(state.copyWith(status: CalibrationState.sampling));
      await _sseSub?.cancel();
      _sseSub = _progressStream(sessionId).listen(
        (p) => add(CalibrationProgressReceived(p)),
        onError: (Object e) => add(CalibrationSseError(e.toString())),
        onDone: () => add(const CalibrationSseEnded()),
      );
    } catch (e) {
      emit(state.copyWith(
        status: CalibrationState.error,
        errorMessage: e.toString(),
      ));
    }
  }

  void _onProgress(
    CalibrationProgressReceived event,
    Emitter<CalibrationBlocState> emit,
  ) {
    if (state.status != CalibrationState.sampling) return;
    emit(state.copyWith(progress: event.payload));
  }

  void _onSseEnded(
    CalibrationSseEnded event,
    Emitter<CalibrationBlocState> emit,
  ) {
    // Le stream se ferme naturellement après finalize/abort (`done`,
    // `aborted`, `error`) — on n'a rien à faire dans ces cas. Si on est
    // toujours en `sampling`, c'est anormal (déconnexion réseau, backend
    // crash) : on bascule en error et l'utilisateur peut redémarrer.
    if (state.status == CalibrationState.sampling) {
      emit(state.copyWith(
        status: CalibrationState.error,
        errorMessage: 'Stream SSE interrompu',
      ));
    }
  }

  void _onSseError(
    CalibrationSseError event,
    Emitter<CalibrationBlocState> emit,
  ) {
    if (state.status == CalibrationState.sampling) {
      emit(state.copyWith(
        status: CalibrationState.error,
        errorMessage: event.message,
      ));
    }
  }

  Future<void> _onFinalize(
    CalibrationFinalizeRequested event,
    Emitter<CalibrationBlocState> emit,
  ) async {
    if (state.status != CalibrationState.sampling) return;
    emit(state.copyWith(status: CalibrationState.computing));
    try {
      final status = await _api.finalizeCalibration(_sensorId);
      emit(state.copyWith(
        status: CalibrationState.done,
        finalizedStatus: status,
      ));
    } catch (e) {
      emit(state.copyWith(
        status: CalibrationState.error,
        errorMessage: e.toString(),
      ));
    }
  }

  Future<void> _onAbort(
    CalibrationAbortRequested event,
    Emitter<CalibrationBlocState> emit,
  ) async {
    try {
      await _api.abortCalibration(_sensorId);
      emit(state.copyWith(
        status: CalibrationState.aborted,
        errorMessage: null,
      ));
    } catch (e) {
      emit(state.copyWith(
        status: CalibrationState.error,
        errorMessage: e.toString(),
      ));
    }
  }

  @override
  Future<void> close() async {
    await _sseSub?.cancel();
    _sseSub = null;
    return super.close();
  }
}
