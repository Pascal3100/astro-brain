/// Modèles Dart miroir des payloads Pydantic de calibration du backend.
///
/// Correspondance JSON → Dart :
///   `bias`, `offsets` → record `(double, double, double)` (Dart 3 records)
///   `scale_matrix`    → `List<List<double>>` 3×3
///   `calibrated_at`   → `DateTime?` via `DateTime.parse`
///   `payload`         → `Object?` (Adxl345Offsets | Lis3mdlOffsets | null)
///     les appelants discriminent via `is Adxl345Offsets` / `is Lis3mdlOffsets`.
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
// Adxl345Offsets
// ---------------------------------------------------------------------------

/// Offsets de calibration pour un capteur ADXL345.
///
/// Champs :
/// - [bias] : triplet d'offset (x, y, z) en g.
/// - [sigma] : écart-type résiduel après calibration.
/// - [zeroAltDeg] : angle d'altitude à zéro en degrés (optionnel).
class Adxl345Offsets extends Equatable {
  const Adxl345Offsets({
    required this.bias,
    required this.sigma,
    this.zeroAltDeg,
  });

  /// Offset (x, y, z) en g.
  final (double, double, double) bias;

  /// Écart-type résiduel.
  final double sigma;

  /// Altitude correspondant au zéro capteur, en degrés.
  final double? zeroAltDeg;

  factory Adxl345Offsets.fromJson(Map<String, dynamic> json) {
    final list = (json['bias'] as List).cast<num>();
    return Adxl345Offsets(
      bias: (list[0].toDouble(), list[1].toDouble(), list[2].toDouble()),
      sigma: (json['sigma'] as num).toDouble(),
      zeroAltDeg: (json['zero_alt_deg'] as num?)?.toDouble(),
    );
  }

  @override
  List<Object?> get props => [bias, sigma, zeroAltDeg];
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
/// `Adxl345Offsets | Lis3mdlOffsets | null`.
/// Les appelants doivent discriminer via `is Adxl345Offsets` ou
/// `is Lis3mdlOffsets`.
///
/// La désérialisation du payload est guidée par [sensorId] :
///   - `'lis3mdl'` → [Lis3mdlOffsets.fromJson]
///   - tout autre → [Adxl345Offsets.fromJson]
class CalibrationStatus extends Equatable {
  const CalibrationStatus({
    required this.sensorId,
    required this.calibratedAt,
    required this.payload,
  });

  /// Identifiant du capteur (ex. `'adxl345_mount'`, `'lis3mdl'`).
  final String sensorId;

  /// Date/heure de la dernière calibration (null si jamais calibré).
  final DateTime? calibratedAt;

  /// Offsets de calibration (null si jamais calibré).
  ///
  /// Type runtime : [Adxl345Offsets], [Lis3mdlOffsets] ou `null`.
  final Object? payload;

  factory CalibrationStatus.fromJson(Map<String, dynamic> json) {
    final sensorId = json['sensor_id'] as String;
    final rawTs = json['calibrated_at'] as String?;
    final rawPayload = json['payload'] as Map<String, dynamic>?;

    final Object? payload;
    if (rawPayload == null) {
      payload = null;
    } else if (sensorId == 'lis3mdl') {
      payload = Lis3mdlOffsets.fromJson(rawPayload);
    } else {
      payload = Adxl345Offsets.fromJson(rawPayload);
    }

    return CalibrationStatus(
      sensorId: sensorId,
      calibratedAt: rawTs != null ? DateTime.parse(rawTs) : null,
      payload: payload,
    );
  }

  @override
  List<Object?> get props => [sensorId, calibratedAt, payload];
}
