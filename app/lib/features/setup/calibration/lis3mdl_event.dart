import 'package:equatable/equatable.dart';

import '../../../models/calibration.dart';

abstract class Lis3mdlEvent extends Equatable {
  const Lis3mdlEvent();
  @override
  List<Object?> get props => const [];
}

/// Démarre la session : POST /start puis ouvre le stream SSE.
class Lis3mdlStarted extends Lis3mdlEvent {
  const Lis3mdlStarted();
}

/// Un nouvel échantillon de progression est arrivé via SSE.
class Lis3mdlProgressReceived extends Lis3mdlEvent {
  const Lis3mdlProgressReceived(this.payload);
  final CalibrationProgress payload;
  @override
  List<Object?> get props => [payload];
}

/// Le stream SSE s'est terminé naturellement (end event ou connexion close).
class Lis3mdlSseEnded extends Lis3mdlEvent {
  const Lis3mdlSseEnded();
}

/// Erreur transport sur le stream SSE.
class Lis3mdlSseError extends Lis3mdlEvent {
  const Lis3mdlSseError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Bouton VALIDER : POST /finalize.
class Lis3mdlFinalizeRequested extends Lis3mdlEvent {
  const Lis3mdlFinalizeRequested();
}

/// Bouton ANNULER : POST /abort.
class Lis3mdlAbortRequested extends Lis3mdlEvent {
  const Lis3mdlAbortRequested();
}
