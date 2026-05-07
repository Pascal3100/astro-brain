/// BLoC pour l'écran « Courses ALT » (item #4 du Setup).
///
/// Cycle de vie :
///   Reloaded (init) → GET /limits/alt → pré-remplit lower/upper si déjà set
///   LowerCaptured(deg) → met à jour `lowerDeg`, reset `isSaved`
///   UpperCaptured(deg) → met à jour `upperDeg`, reset `isSaved`
///   SaveRequested → PUT /limits/alt → `isSaved=true` (200) ou
///     `errorMessage` (422 / autre)
///
/// Note : ré-capturer une borne déjà capturée écrase simplement la valeur ;
/// on ne reset PAS l'autre borne (arbitrage simplicité).
library;

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/limits.dart';
import '../../../services/api_service.dart';
import 'limits_event.dart';
import 'limits_state.dart';

class LimitsAltBloc extends Bloc<LimitsAltEvent, LimitsAltState> {
  LimitsAltBloc({required ApiService api})
      : _api = api,
        super(const LimitsAltState()) {
    on<LimitsAltReloaded>(_onReloaded);
    on<LimitsAltLowerCaptured>(_onLowerCaptured);
    on<LimitsAltUpperCaptured>(_onUpperCaptured);
    on<LimitsAltSaveRequested>(_onSaveRequested);
  }

  final ApiService _api;

  Future<void> _onReloaded(
    LimitsAltReloaded event,
    Emitter<LimitsAltState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, errorMessage: null));
    try {
      final limits = await _api.getAltLimits();
      emit(state.copyWith(
        isLoading: false,
        lowerDeg: limits?.minDeg,
        upperDeg: limits?.maxDeg,
      ));
    } catch (e) {
      // Best-effort : on ne bloque pas l'utilisateur si le GET échoue,
      // il pourra quand même capturer ses bornes.
      emit(state.copyWith(isLoading: false, errorMessage: e.toString()));
    }
  }

  void _onLowerCaptured(
    LimitsAltLowerCaptured event,
    Emitter<LimitsAltState> emit,
  ) {
    emit(state.copyWith(
      lowerDeg: event.altDeg,
      isSaved: false,
      errorMessage: null,
    ));
  }

  void _onUpperCaptured(
    LimitsAltUpperCaptured event,
    Emitter<LimitsAltState> emit,
  ) {
    emit(state.copyWith(
      upperDeg: event.altDeg,
      isSaved: false,
      errorMessage: null,
    ));
  }

  Future<void> _onSaveRequested(
    LimitsAltSaveRequested event,
    Emitter<LimitsAltState> emit,
  ) async {
    if (!state.canSave) return;
    emit(state.copyWith(isSaving: true, errorMessage: null));
    try {
      final saved = await _api.putAltLimits(
        AltLimits(minDeg: state.lowerDeg!, maxDeg: state.upperDeg!),
      );
      emit(state.copyWith(
        isSaving: false,
        isSaved: true,
        lowerDeg: saved.minDeg,
        upperDeg: saved.maxDeg,
      ));
    } on ApiException catch (e) {
      final msg = e.statusCode == 422
          ? 'Plage invalide (min < max et écart ≥ 30°).'
          : 'Erreur réseau (${e.statusCode ?? "?"}).';
      emit(state.copyWith(isSaving: false, errorMessage: msg));
    } catch (e) {
      emit(state.copyWith(isSaving: false, errorMessage: e.toString()));
    }
  }
}
