import 'package:equatable/equatable.dart';

abstract class NetworkEvent extends Equatable {
  const NetworkEvent();
  @override
  List<Object?> get props => const [];
}

class NetworkLoaded extends NetworkEvent {
  const NetworkLoaded();
}

class NetworkHostChanged extends NetworkEvent {
  const NetworkHostChanged(this.host);
  final String host;
  @override
  List<Object?> get props => [host];
}

class NetworkPortChanged extends NetworkEvent {
  const NetworkPortChanged(this.port);
  final int port;
  @override
  List<Object?> get props => [port];
}

class NetworkTestRequested extends NetworkEvent {
  const NetworkTestRequested();
}

class NetworkSaveRequested extends NetworkEvent {
  const NetworkSaveRequested();
}

class NetworkResetRequested extends NetworkEvent {
  const NetworkResetRequested();
}
