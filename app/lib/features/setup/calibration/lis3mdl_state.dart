import 'package:equatable/equatable.dart';

import '../../../models/calibration.dart';

/// Seuils pour activer le bouton VALIDER. Miroir des défauts backend
/// (cf. `services/calibration.py` : `lis3mdl_min_samples=500`,
/// `lis3mdl_coverage_threshold=80.0`).
///
/// Le backend ne gate pas sur `residual` côté finalize ; on reproduit ici
/// uniquement les deux gates effectives (samples + coverage). `residual`
/// est affiché comme métrique mais n'entre pas dans `canFinalize`.
const lis3mdlMinSamples = 500;
const lis3mdlCoverageThreshold = 80.0;

enum Lis3mdlStatus {
  /// État initial, avant que l'utilisateur ait pressé DÉMARRER.
  idle,

  /// Session active, échantillons en cours via SSE.
  sampling,

  /// Finalize en cours (entre POST et 200).
  computing,

  /// Finalize terminé avec succès — l'écran reste affiché pour montrer
  /// le preview heading. Le pop est déclenché par le bouton FERMER.
  done,

  /// Abort terminé avec succès.
  aborted,

  /// Une étape a échoué (start, finalize, abort, ou erreur SSE).
  error,
}

class Lis3mdlState extends Equatable {
  const Lis3mdlState({
    this.status = Lis3mdlStatus.idle,
    this.progress,
    this.errorMessage,
    this.finalizedStatus,
  });

  final Lis3mdlStatus status;
  final CalibrationProgress? progress;
  final String? errorMessage;
  final CalibrationStatus? finalizedStatus;

  /// Le bouton VALIDER est actif uniquement pendant l'échantillonnage,
  /// quand on a au moins [lis3mdlMinSamples] échantillons et une
  /// couverture sphérique >= [lis3mdlCoverageThreshold] %.
  ///
  /// On NE gate PAS sur `residual` : le backend ne le fait pas non plus.
  bool get canFinalize =>
      status == Lis3mdlStatus.sampling &&
      progress != null &&
      progress!.samplesN >= lis3mdlMinSamples &&
      progress!.coveragePct >= lis3mdlCoverageThreshold;

  Lis3mdlState copyWith({
    Lis3mdlStatus? status,
    Object? progress = _sentinel,
    Object? errorMessage = _sentinel,
    Object? finalizedStatus = _sentinel,
  }) => Lis3mdlState(
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
  );

  @override
  List<Object?> get props => [status, progress, errorMessage, finalizedStatus];
}

const _sentinel = Object();
