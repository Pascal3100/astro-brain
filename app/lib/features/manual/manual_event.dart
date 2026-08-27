import 'package:equatable/equatable.dart';

import '../../services/api_service.dart';

sealed class ManualEvent extends Equatable {
  const ManualEvent();
  @override
  List<Object?> get props => const [];
}

class ManualRateChanged extends ManualEvent {
  const ManualRateChanged(this.rate);
  final int rate;
  @override
  List<Object> get props => [rate];
}

class ManualSlewPressed extends ManualEvent {
  const ManualSlewPressed({required this.axis, required this.direction});
  final Axis axis;
  final Direction direction;
  @override
  List<Object> get props => [axis, direction];
}

class ManualSlewReleased extends ManualEvent {
  const ManualSlewReleased(this.axis);
  final Axis axis;
  @override
  List<Object> get props => [axis];
}

/// Demande une reconnexion de la monture (bouton de la bannière d'erreur).
class ManualReconnectPressed extends ManualEvent {
  const ManualReconnectPressed();
}
