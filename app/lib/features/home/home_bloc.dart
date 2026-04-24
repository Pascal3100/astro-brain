import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import 'home_event.dart';
import 'home_state.dart';

export 'home_event.dart';
export 'home_state.dart';

class HomeBloc extends Bloc<HomeEvent, HomeState> {
  HomeBloc({required this.api}) : super(const HomeState()) {
    on<HomeRateChanged>(
      (e, emit) => emit(state.copyWith(rate: e.rate.clamp(1, 9))),
    );
    on<HomeSlewPressed>(_onSlew);
    on<HomeSlewReleased>(_onStop);
    on<HomeTrackingToggled>(_onTracking);
  }

  final ApiService api;

  Future<void> _onSlew(HomeSlewPressed e, Emitter<HomeState> emit) async {
    try {
      await api.slew(axis: e.axis, direction: e.direction, rate: state.rate);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onStop(HomeSlewReleased e, Emitter<HomeState> emit) async {
    try {
      await api.stop(axis: e.axis);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onTracking(
    HomeTrackingToggled e,
    Emitter<HomeState> emit,
  ) async {
    try {
      await api.setTracking(e.enabled);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }
}
