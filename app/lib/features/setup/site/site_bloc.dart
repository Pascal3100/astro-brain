/// BLoC de la carte Site d'observation (Setup).
library;

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../alignment/phone_location.dart';
import 'site_event.dart';
import 'site_repository.dart';
import 'site_state.dart';

/// Lit et écrit le site d'observation persisté sur le Pi.
///
/// [phoneLocation] est injecté (fake en tests) : c'est la seule façon de
/// renseigner le site en v1, le Pi n'ayant plus de GPS depuis le retrait du
/// module DroTek. L'écriture n'a lieu que sur action explicite de
/// l'utilisateur — jamais en tâche de fond — pour ne pas invalider un
/// alignement valide via la garde ΔGPS 20 m du backend.
class SiteBloc extends Bloc<SiteEvent, SiteState> {
  SiteBloc({
    required this.repo,
    PhoneLocation? phoneLocation,
  })  : _phoneLocation = phoneLocation ?? const GeolocatorPhoneLocation(),
        super(const SiteState()) {
    on<SiteLoaded>(_onLoaded);
    on<SiteFromPhoneRequested>(_onFromPhone);
  }

  final SiteRepository repo;
  final PhoneLocation _phoneLocation;

  Future<void> _onLoaded(SiteLoaded e, Emitter<SiteState> emit) async {
    emit(state.copyWith(status: SiteStatus.loading, error: null));
    try {
      final site = await repo.getSite();
      emit(SiteState(status: SiteStatus.ready, site: site));
    } on Exception catch (err) {
      emit(state.copyWith(status: SiteStatus.error, error: '$err'));
    }
  }

  Future<void> _onFromPhone(
    SiteFromPhoneRequested e,
    Emitter<SiteState> emit,
  ) async {
    emit(state.copyWith(status: SiteStatus.saving, error: null));
    final pos = await _phoneLocation.current();
    if (pos == null) {
      emit(state.copyWith(
        status: SiteStatus.error,
        error: 'Position indisponible — permission refusée ou GPS éteint.',
      ));
      return;
    }
    try {
      await repo.putSite(pos.lat, pos.lon);
      final site = await repo.getSite();
      emit(SiteState(status: SiteStatus.ready, site: site));
    } on Exception catch (err) {
      emit(state.copyWith(status: SiteStatus.error, error: '$err'));
    }
  }
}
