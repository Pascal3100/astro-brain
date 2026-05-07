import 'package:equatable/equatable.dart';

import '../../../models/calibration.dart';

abstract class AdxlTubeEvent extends Equatable {
  const AdxlTubeEvent();
  @override
  List<Object?> get props => const [];
}

/// Démarre la session : POST /start puis ouvre le stream SSE.
class AdxlTubeStarted extends AdxlTubeEvent {
  const AdxlTubeStarted();
}

/// Un nouvel échantillon de progression est arrivé via SSE.
class AdxlTubeProgressReceived extends AdxlTubeEvent {
  const AdxlTubeProgressReceived(this.payload);
  final CalibrationProgress payload;
  @override
  List<Object?> get props => [payload];
}

/// Le stream SSE s'est terminé naturellement (end event ou connexion close).
class AdxlTubeSseEnded extends AdxlTubeEvent {
  const AdxlTubeSseEnded();
}

/// Erreur transport sur le stream SSE.
class AdxlTubeSseError extends AdxlTubeEvent {
  const AdxlTubeSseError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Bouton VALIDER : POST /finalize.
class AdxlTubeFinalizeRequested extends AdxlTubeEvent {
  const AdxlTubeFinalizeRequested();
}

/// Bouton ANNULER : POST /abort.
class AdxlTubeAbortRequested extends AdxlTubeEvent {
  const AdxlTubeAbortRequested();
}
