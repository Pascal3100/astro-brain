import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import 'splash_state.dart';

class SplashCubit extends Cubit<SplashState> {
  SplashCubit({
    required this.api,
    required this.appBloc,
    this.minPhaseDuration = const Duration(milliseconds: 500),
    this.successHoldDuration = const Duration(milliseconds: 600),
  }) : super(const SplashState.initial());

  final ApiService api;
  final AppBloc appBloc;

  /// Durée minimale d'affichage de chaque phase. Évite l'effet « ghost screen »
  /// quand le backend répond très vite : on garantit qu'on voit chaque étape
  /// se cocher avant de basculer sur Home. Mis à zéro dans les tests.
  final Duration minPhaseDuration;

  /// Délai supplémentaire après la dernière phase, pendant lequel les 3 lignes
  /// sont vertes (✓), avant de basculer sur Home. Donne un sentiment de
  /// « tout vérifié » plutôt qu'un cut sec.
  final Duration successHoldDuration;

  Future<void> start() async {
    emit(state.copyWith(phase: SplashPhase.contacting));
    try {
      await Future.wait<void>([
        api.fetchState(),
        Future<void>.delayed(minPhaseDuration),
      ]);
      emit(state.copyWith(phase: SplashPhase.loading));
      await Future<void>.delayed(minPhaseDuration);
      emit(state.copyWith(phase: SplashPhase.openingStream));
      appBloc.add(const AppStarted());
      await Future<void>.delayed(minPhaseDuration);
      await Future<void>.delayed(successHoldDuration);
      emit(state.copyWith(phase: SplashPhase.success));
    } on Exception catch (e) {
      emit(state.copyWith(
        phase: SplashPhase.failure,
        errorMessage: e.toString(),
      ));
    }
  }

  void continueOffline() {
    appBloc.add(const AppStarted());
    emit(state.copyWith(phase: SplashPhase.success));
  }
}
