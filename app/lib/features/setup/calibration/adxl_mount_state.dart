import 'package:equatable/equatable.dart';

import '../../../models/calibration.dart';

/// Seuils pour activer le bouton VALIDER. Miroir des défauts backend
/// (cf. `services/calibration.py` : `adxl_min_samples=100`,
/// `adxl_sigma_threshold=0.05`).
const adxlMinSamples = 100;
const adxlSigmaThreshold = 0.05;

enum AdxlMountStatus {
  /// État initial, avant que l'utilisateur ait pressé DÉMARRER.
  idle,

  /// Session active, échantillons en cours via SSE.
  sampling,

  /// Finalize en cours (entre POST et 200).
  computing,

  /// Finalize terminé avec succès.
  done,

  /// Abort terminé avec succès.
  aborted,

  /// Une étape a échoué (start, finalize, abort, ou erreur SSE).
  error,
}

class AdxlMountState extends Equatable {
  const AdxlMountState({
    this.status = AdxlMountStatus.idle,
    this.progress,
    this.errorMessage,
    this.finalizedStatus,
  });

  final AdxlMountStatus status;
  final CalibrationProgress? progress;
  final String? errorMessage;
  final CalibrationStatus? finalizedStatus;

  /// Le bouton VALIDER est actif uniquement pendant l'échantillonnage,
  /// quand on a au moins [adxlMinSamples] échantillons et un sigma
  /// strictement inférieur au seuil.
  bool get canFinalize =>
      status == AdxlMountStatus.sampling &&
      progress != null &&
      progress!.samplesN >= adxlMinSamples &&
      progress!.sigma < adxlSigmaThreshold;

  AdxlMountState copyWith({
    AdxlMountStatus? status,
    Object? progress = _sentinel,
    Object? errorMessage = _sentinel,
    Object? finalizedStatus = _sentinel,
  }) => AdxlMountState(
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
