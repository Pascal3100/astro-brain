import 'package:equatable/equatable.dart';

import '../../models/system_state.dart';

sealed class AppEvent extends Equatable {
  const AppEvent();
  @override
  List<Object?> get props => const [];
}

/// Émis au `initState` du widget racine — démarre le service SSE.
class AppStarted extends AppEvent {
  const AppStarted();
}

/// Émis en interne quand le service SSE livre un nouvel état.
class AppSystemStateReceived extends AppEvent {
  const AppSystemStateReceived(this.systemState);
  final SystemState systemState;
  @override
  List<Object> get props => [systemState];
}

/// Émis en interne quand le service SSE tombe en erreur.
class AppConnectionLost extends AppEvent {
  const AppConnectionLost();
}

/// Émis par l'utilisateur pour déclencher une reconnexion manuelle.
class AppReconnectRequested extends AppEvent {
  const AppReconnectRequested();
}
