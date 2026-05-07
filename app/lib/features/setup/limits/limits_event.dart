import 'package:equatable/equatable.dart';

abstract class LimitsAltEvent extends Equatable {
  const LimitsAltEvent();
  @override
  List<Object?> get props => const [];
}

/// Initial : `GET /limits/alt`. Pré-remplit les boutons si déjà set.
class LimitsAltReloaded extends LimitsAltEvent {
  const LimitsAltReloaded();
}

/// Snapshot ALT_min via le bouton « POINTER LE PLUS BAS ».
class LimitsAltLowerCaptured extends LimitsAltEvent {
  const LimitsAltLowerCaptured(this.altDeg);
  final double altDeg;
  @override
  List<Object?> get props => [altDeg];
}

/// Snapshot ALT_max via le bouton « POINTER LE PLUS HAUT ».
class LimitsAltUpperCaptured extends LimitsAltEvent {
  const LimitsAltUpperCaptured(this.altDeg);
  final double altDeg;
  @override
  List<Object?> get props => [altDeg];
}

/// Bouton « ENREGISTRER » : `PUT /limits/alt`.
class LimitsAltSaveRequested extends LimitsAltEvent {
  const LimitsAltSaveRequested();
}
