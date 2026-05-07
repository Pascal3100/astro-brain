/// Modèles Dart miroir des payloads SSE des streams de capteurs.
///
/// Correspondance JSON → Dart :
///   `ts`               → `DateTime` via `DateTime.parse`
///   `pitch_deg`/`roll_deg`/`magnitude_g` → `double`
///   `heading_deg`/`magnitude_uT`         → `double`
///   `raw` (objet `{x,y,z}`)              → record `(double, double, double)`
///   `tilt_compensated`/`calibrated`      → `bool`
library;

import 'package:equatable/equatable.dart';

// ---------------------------------------------------------------------------
// TiltReading
// ---------------------------------------------------------------------------

/// Lecture inclinaison instantanée (ADXL345 monté).
///
/// Champs :
/// - [ts] : horodatage backend.
/// - [pitchDeg] : pitch en degrés (rotation autour de l'axe Y).
/// - [rollDeg] : roll en degrés (rotation autour de l'axe X).
/// - [magnitudeG] : norme du vecteur d'accélération en g (≈1.0 au repos).
/// - [calibrated] : `true` si la calibration a été appliquée.
class TiltReading extends Equatable {
  const TiltReading({
    required this.ts,
    required this.pitchDeg,
    required this.rollDeg,
    required this.magnitudeG,
    required this.calibrated,
  });

  final DateTime ts;
  final double pitchDeg;
  final double rollDeg;
  final double magnitudeG;
  final bool calibrated;

  factory TiltReading.fromJson(Map<String, dynamic> json) {
    return TiltReading(
      ts: DateTime.parse(json['ts'] as String),
      pitchDeg: (json['pitch_deg'] as num).toDouble(),
      rollDeg: (json['roll_deg'] as num).toDouble(),
      magnitudeG: (json['magnitude_g'] as num).toDouble(),
      calibrated: json['calibrated'] as bool,
    );
  }

  @override
  List<Object?> get props => [ts, pitchDeg, rollDeg, magnitudeG, calibrated];
}

// ---------------------------------------------------------------------------
// CompassReading
// ---------------------------------------------------------------------------

/// Lecture compas instantanée (LIS3MDL + compensation par ADXL mount).
///
/// Champs :
/// - [ts] : horodatage backend.
/// - [headingDeg] : cap en degrés (0 = nord).
/// - [magnitudeUt] : norme du vecteur magnétique en µT.
/// - [raw] : triplet brut (x, y, z) en µT (avant tilt-compensation).
/// - [tiltCompensated] : `true` si l'inclinaison du tube est compensée.
/// - [calibrated] : `true` si la calibration a été appliquée.
class CompassReading extends Equatable {
  const CompassReading({
    required this.ts,
    required this.headingDeg,
    required this.magnitudeUt,
    required this.raw,
    required this.tiltCompensated,
    required this.calibrated,
  });

  final DateTime ts;
  final double headingDeg;
  final double magnitudeUt;
  final (double, double, double) raw;
  final bool tiltCompensated;
  final bool calibrated;

  factory CompassReading.fromJson(Map<String, dynamic> json) {
    final rawMap = json['raw'] as Map<String, dynamic>;
    return CompassReading(
      ts: DateTime.parse(json['ts'] as String),
      headingDeg: (json['heading_deg'] as num).toDouble(),
      magnitudeUt: (json['magnitude_uT'] as num).toDouble(),
      raw: (
        (rawMap['x'] as num).toDouble(),
        (rawMap['y'] as num).toDouble(),
        (rawMap['z'] as num).toDouble(),
      ),
      tiltCompensated: json['tilt_compensated'] as bool,
      calibrated: json['calibrated'] as bool,
    );
  }

  @override
  List<Object?> get props => [
    ts,
    headingDeg,
    magnitudeUt,
    raw,
    tiltCompensated,
    calibrated,
  ];
}
