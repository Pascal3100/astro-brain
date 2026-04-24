import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/event_stream_service.dart';
import 'app_event.dart';
import 'app_state.dart';

export 'app_event.dart';
export 'app_state.dart';

class AppBloc extends Bloc<AppEvent, AppState> {
  AppBloc({required EventStreamService eventStream})
      : _eventStream = eventStream,
        super(const AppState.initial()) {
    on<AppStarted>(_onStarted);
    on<AppSystemStateReceived>(_onSystemStateReceived);
    on<AppConnectionLost>(_onConnectionLost);
  }

  final EventStreamService _eventStream;
  StreamSubscription<Object>? _sub;

  Future<void> _onStarted(AppStarted e, Emitter<AppState> emit) async {
    _sub?.cancel();
    _sub = _eventStream.stream.listen(
      (sys) => add(AppSystemStateReceived(sys)),
      onError: (_) => add(const AppConnectionLost()),
    );
    _eventStream.start();
  }

  void _onSystemStateReceived(
      AppSystemStateReceived e, Emitter<AppState> emit) {
    emit(state.copyWith(
      connection: ConnectionStatus.connected,
      system: e.systemState,
    ));
  }

  void _onConnectionLost(AppConnectionLost e, Emitter<AppState> emit) {
    emit(state.copyWith(connection: ConnectionStatus.offline));
  }

  @override
  Future<void> close() async {
    await _sub?.cancel();
    await _eventStream.stop();
    return super.close();
  }
}
