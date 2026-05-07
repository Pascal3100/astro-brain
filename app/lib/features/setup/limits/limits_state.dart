import 'package:equatable/equatable.dart';

/// Écart minimum (degrés) entre ALT_min et ALT_max — miroir de la règle
/// backend (`AltLimits.model_validator`). Sous ce seuil, le bouton
/// ENREGISTRER reste désactivé et un warning inline est affiché.
const double kAltLimitsMinRangeDeg = 30.0;

const _sentinel = Object();

class LimitsAltState extends Equatable {
  const LimitsAltState({
    this.lowerDeg,
    this.upperDeg,
    this.isLoading = false,
    this.isSaving = false,
    this.isSaved = false,
    this.errorMessage,
  });

  /// `null` tant que pas capturé (ou jamais set côté backend).
  final double? lowerDeg;
  final double? upperDeg;

  /// `true` pendant le `GET /limits/alt` initial.
  final bool isLoading;

  /// `true` pendant le `PUT /limits/alt`.
  final bool isSaving;

  /// `true` après un PUT 200. Reset à `false` à la prochaine capture.
  final bool isSaved;

  /// Message d'erreur (422 ou autre) — `null` quand tout va bien.
  final String? errorMessage;

  /// Le bouton ENREGISTRER s'active quand les deux valeurs sont capturées
  /// et que l'écart respecte le seuil [kAltLimitsMinRangeDeg].
  bool get canSave {
    final l = lowerDeg;
    final u = upperDeg;
    if (l == null || u == null) return false;
    if (isSaving) return false;
    return (u - l) >= kAltLimitsMinRangeDeg;
  }

  /// `true` quand les deux valeurs sont capturées mais l'écart est trop
  /// faible — sert à afficher le warning inline.
  bool get hasRangeWarning {
    final l = lowerDeg;
    final u = upperDeg;
    if (l == null || u == null) return false;
    return (u - l) < kAltLimitsMinRangeDeg;
  }

  LimitsAltState copyWith({
    Object? lowerDeg = _sentinel,
    Object? upperDeg = _sentinel,
    bool? isLoading,
    bool? isSaving,
    bool? isSaved,
    Object? errorMessage = _sentinel,
  }) => LimitsAltState(
        lowerDeg: identical(lowerDeg, _sentinel)
            ? this.lowerDeg
            : lowerDeg as double?,
        upperDeg: identical(upperDeg, _sentinel)
            ? this.upperDeg
            : upperDeg as double?,
        isLoading: isLoading ?? this.isLoading,
        isSaving: isSaving ?? this.isSaving,
        isSaved: isSaved ?? this.isSaved,
        errorMessage: identical(errorMessage, _sentinel)
            ? this.errorMessage
            : errorMessage as String?,
      );

  @override
  List<Object?> get props =>
      [lowerDeg, upperDeg, isLoading, isSaving, isSaved, errorMessage];
}
