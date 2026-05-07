/// Modèle Dart miroir du payload Pydantic `AltLimits` du backend.
///
/// Correspondance JSON → Dart :
///   `min_deg` → `minDeg`
///   `max_deg` → `maxDeg`
library;

import 'package:equatable/equatable.dart';

/// Limites mécaniques d'altitude de la monture en degrés.
///
/// Contraintes (validées côté backend, pas dupliquées ici) :
/// - `minDeg < maxDeg`
/// - `(maxDeg - minDeg) >= 30`
class AltLimits extends Equatable {
  const AltLimits({required this.minDeg, required this.maxDeg});

  final double minDeg;
  final double maxDeg;

  factory AltLimits.fromJson(Map<String, dynamic> json) => AltLimits(
        minDeg: (json['min_deg'] as num).toDouble(),
        maxDeg: (json['max_deg'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'min_deg': minDeg,
        'max_deg': maxDeg,
      };

  @override
  List<Object?> get props => [minDeg, maxDeg];
}
