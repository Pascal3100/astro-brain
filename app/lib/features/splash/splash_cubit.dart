import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import 'splash_state.dart';

class SplashCubit extends Cubit<SplashState> {
  SplashCubit({required this.api, required this.appBloc})
      : super(const SplashState.initial());

  final ApiService api;
  final AppBloc appBloc;

  Future<void> start() async {
    emit(state.copyWith(phase: SplashPhase.contacting));
    try {
      await api.fetchState();
      emit(state.copyWith(phase: SplashPhase.loading));
      emit(state.copyWith(phase: SplashPhase.openingStream));
      appBloc.add(const AppStarted());
      emit(state.copyWith(phase: SplashPhase.success));
    } on Exception catch (e) {
      emit(state.copyWith(
        phase: SplashPhase.failure,
        errorMessage: e.toString(),
      ));
    }
  }

  void continueOffline() {
    emit(state.copyWith(phase: SplashPhase.success));
  }
}
