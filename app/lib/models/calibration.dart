/// Modèles Dart miroir des payloads Pydantic de calibration du backend.
///
/// Correspondance JSON → Dart :
///   `bias`, `offsets` → record `(double, double, double)` (Dart 3 records)
///   `scale_matrix`    → `List<List<double>>` 3×3
///   `calibrated_at`   → `DateTime?` via `DateTime.parse`
///   `payload`         → `Object?` (Lis3mdlOffsets | null)
library;

import 'package:equatable/equatable.dart';

// ---------------------------------------------------------------------------
// CalibrationState
// ---------------------------------------------------------------------------

/// État d'une session de calibration (miroir du Literal Python côté backend).
enum CalibrationState {
  idle,
  sampling,
  computing,
  done,
  aborted,
  error;

  /// Désérialise depuis une chaîne JSON.
  ///
  /// Retourne [CalibrationState.idle] pour toute valeur inconnue (défensif).
  static CalibrationState fromJson(String s) =>
      CalibrationState.values.firstWhere(
        (e) => e.name == s,
        orElse: () => CalibrationState.idle,
      );
}

// ---------------------------------------------------------------------------
// Lis3mdlOffsets
// ---------------------------------------------------------------------------

/// Offsets de calibration pour le magnétomètre LIS3MDL.
///
/// Champs :
/// - [offsets] : triplet d'offset hard-iron (x, y, z).
/// - [scaleMatrix] : matrice soft-iron 3×3.
/// - [coveragePct] : couverture sphérique des échantillons en %.
/// - [residual] : résidu moyen après correction.
class Lis3mdlOffsets extends Equatable {
  const Lis3mdlOffsets({
    required this.offsets,
    required this.scaleMatrix,
    required this.coveragePct,
    required this.residual,
  });

  /// Offset hard-iron (x, y, z).
  final (double, double, double) offsets;

  /// Matrice soft-iron 3×3. Toujours de longueur 3, chaque sous-liste de
  /// longueur 3.
  final List<List<double>> scaleMatrix;

  /// Couverture sphérique des points de calibration en %.
  final double coveragePct;

  /// Résidu moyen après correction.
  final double residual;

  factory Lis3mdlOffsets.fromJson(Map<String, dynamic> json) {
    final offList = (json['offsets'] as List).cast<num>();
    final rawMatrix = json['scale_matrix'] as List;
    final matrix = rawMatrix
        .map((row) => (row as List).cast<num>().map((v) => v.toDouble()).toList())
        .toList();
    return Lis3mdlOffsets(
      offsets: (
        offList[0].toDouble(),
        offList[1].toDouble(),
        offList[2].toDouble(),
      ),
      scaleMatrix: matrix,
      coveragePct: (json['coverage_pct'] as num).toDouble(),
      residual: (json['residual'] as num).toDouble(),
    );
  }

  @override
  List<Object?> get props => [offsets, scaleMatrix, coveragePct, residual];
}

// ---------------------------------------------------------------------------
// CalibrationProgress
// ---------------------------------------------------------------------------

/// Progression en temps réel d'une session de calibration (stream SSE).
class CalibrationProgress extends Equatable {
  const CalibrationProgress({
    required this.state,
    required this.samplesN,
    required this.coveragePct,
    required this.sigma,
    this.hint,
    this.residual,
  });

  /// État courant de la session.
  final CalibrationState state;

  /// Nombre d'échantillons collectés.
  final int samplesN;

  /// Couverture sphérique en %.
  final double coveragePct;

  /// Écart-type courant.
  final double sigma;

  /// Message d'aide contextuel (peut être null).
  final String? hint;

  /// Résidu courant (disponible seulement en phase computing/done).
  final double? residual;

  factory CalibrationProgress.fromJson(Map<String, dynamic> json) {
    return CalibrationProgress(
      state: CalibrationState.fromJson(json['state'] as String),
      samplesN: json['samples_n'] as int,
      coveragePct: (json['coverage_pct'] as num).toDouble(),
      sigma: (json['sigma'] as num).toDouble(),
      hint: json['hint'] as String?,
      residual: (json['residual'] as num?)?.toDouble(),
    );
  }

  @override
  List<Object?> get props =>
      [state, samplesN, coveragePct, sigma, hint, residual];
}

// ---------------------------------------------------------------------------
// CalibrationStatus
// ---------------------------------------------------------------------------

/// Statut persisté d'un capteur calibré.
///
/// [payload] est typé `Object?` pour représenter l'union
/// `Lis3mdlOffsets | null` (seul le capteur `'lis3mdl'` reste calibrable
/// côté app — la calibration ADXL345 a été retirée, cf. ADR 2026-07-17).
class CalibrationStatus extends Equatable {
  const CalibrationStatus({
    required this.sensorId,
    required this.calibratedAt,
    required this.payload,
  });

  /// Identifiant du capteur (ex. `'lis3mdl'`).
  final String sensorId;

  /// Date/heure de la dernière calibration (null si jamais calibré).
  final DateTime? calibratedAt;

  /// Offsets de calibration (null si jamais calibré).
  ///
  /// Type runtime : [Lis3mdlOffsets] ou `null`.
  final Object? payload;

  factory CalibrationStatus.fromJson(Map<String, dynamic> json) {
    final sensorId = json['sensor_id'] as String;
    final rawTs = json['calibrated_at'] as String?;
    final rawPayload = json['payload'] as Map<String, dynamic>?;

    final Object? payload = rawPayload == null
        ? null
        : Lis3mdlOffsets.fromJson(rawPayload);

    return CalibrationStatus(
      sensorId: sensorId,
      calibratedAt: rawTs != null ? DateTime.parse(rawTs) : null,
      payload: payload,
    );
  }

  @override
  List<Object?> get props => [sensorId, calibratedAt, payload];
}
