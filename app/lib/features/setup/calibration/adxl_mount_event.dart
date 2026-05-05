import 'package:equatable/equatable.dart';

import '../../../models/calibration.dart';

abstract class AdxlMountEvent extends Equatable {
  const AdxlMountEvent();
  @override
  List<Object?> get props => const [];
}

/// Démarre la session : POST /start puis ouvre le stream SSE.
class AdxlMountStarted extends AdxlMountEvent {
  const AdxlMountStarted();
}

/// Un nouvel échantillon de progression est arrivé via SSE.
class AdxlMountProgressReceived extends AdxlMountEvent {
  const AdxlMountProgressReceived(this.payload);
  final CalibrationProgress payload;
  @override
  List<Object?> get props => [payload];
}

/// Le stream SSE s'est terminé naturellement (end event ou connexion close).
class AdxlMountSseEnded extends AdxlMountEvent {
  const AdxlMountSseEnded();
}

/// Erreur transport sur le stream SSE.
class AdxlMountSseError extends AdxlMountEvent {
  const AdxlMountSseError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Bouton VALIDER : POST /finalize.
class AdxlMountFinalizeRequested extends AdxlMountEvent {
  const AdxlMountFinalizeRequested();
}

/// Bouton ANNULER : POST /abort.
class AdxlMountAbortRequested extends AdxlMountEvent {
  const AdxlMountAbortRequested();
}
