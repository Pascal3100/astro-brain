import 'package:equatable/equatable.dart';

import '../../models/overall_status.dart';
import '../../models/system_state.dart';

enum ConnectionStatus { connecting, connected, offline }

class AppState extends Equatable {
  const AppState({
    required this.connection,
    this.system,
  });

  const AppState.initial()
      : connection = ConnectionStatus.connecting,
        system = null;

  final ConnectionStatus connection;
  final SystemState? system;

  /// `overall` effectif côté UI : offline l'emporte sur les règles backend.
  OverallStatus get effectiveOverall => connection == ConnectionStatus.offline
      ? OverallStatus.offline
      : system?.overall ?? OverallStatus.blue;

  AppState copyWith({ConnectionStatus? connection, SystemState? system}) {
    return AppState(
      connection: connection ?? this.connection,
      system: system ?? this.system,
    );
  }

  @override
  List<Object?> get props => [connection, system];
}
