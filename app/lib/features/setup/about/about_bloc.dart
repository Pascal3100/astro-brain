/// BLoC pour l'écran « À propos » (item #9 du Setup).
///
/// Cycle de vie :
///   AboutLoaded (init)        → GET /about → remplit [AboutState.info]
///   AboutRefreshRequested     → même fetch, re-demandé par le bouton RAFRAÎCHIR
library;

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../services/api_service.dart';
import 'about_event.dart';
import 'about_state.dart';

class AboutBloc extends Bloc<AboutEvent, AboutState> {
  AboutBloc({required ApiService api})
      : _api = api,
        super(const AboutState()) {
    on<AboutLoaded>(_onFetch);
    on<AboutRefreshRequested>(_onFetch);
  }

  final ApiService _api;

  Future<void> _onFetch(
    AboutEvent event,
    Emitter<AboutState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, errorMessage: null));
    try {
      final info = await _api.getAbout();
      emit(state.copyWith(isLoading: false, info: info));
    } catch (e) {
      emit(state.copyWith(isLoading: false, errorMessage: e.toString()));
    }
  }
}
