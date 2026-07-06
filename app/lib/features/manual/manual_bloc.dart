import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import 'manual_event.dart';
import 'manual_state.dart';

export 'manual_event.dart';
export 'manual_state.dart';

class ManualBloc extends Bloc<ManualEvent, ManualState> {
  ManualBloc({required this.api}) : super(const ManualState()) {
    on<ManualRateChanged>(
      // 1..8 : le driver INDI n'expose que 1x…8x (pas de 9x). Un rate 9
      // faisait échouer le slew côté backend en silence (journal S38).
      (e, emit) => emit(state.copyWith(rate: e.rate.clamp(1, 8))),
    );
    on<ManualSlewPressed>(_onSlew);
    on<ManualSlewReleased>(_onStop);
    on<ManualTrackingToggled>(_onTracking);
    on<ManualReconnectPressed>(_onReconnect);
  }

  final ApiService api;

  Future<void> _onSlew(ManualSlewPressed e, Emitter<ManualState> emit) async {
    try {
      await api.slew(axis: e.axis, direction: e.direction, rate: state.rate);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onStop(ManualSlewReleased e, Emitter<ManualState> emit) async {
    try {
      await api.stop(axis: e.axis);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onTracking(
    ManualTrackingToggled e,
    Emitter<ManualState> emit,
  ) async {
    try {
      await api.setTracking(e.enabled);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onReconnect(
    ManualReconnectPressed e,
    Emitter<ManualState> emit,
  ) async {
    try {
      await api.reconnectMount();
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }
}
