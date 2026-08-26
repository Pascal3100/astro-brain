import 'package:equatable/equatable.dart';

import 'site_repository.dart';

enum SiteStatus {
  /// Lecture initiale en cours.
  loading,

  /// Lecture faite — [SiteState.site] vaut `null` si aucun site n'est réglé.
  ready,

  /// Écriture en cours (GPS téléphone puis `PUT /site`).
  saving,

  /// La dernière opération a échoué — voir [SiteState.error].
  error,
}

class SiteState extends Equatable {
  const SiteState({
    this.status = SiteStatus.loading,
    this.site,
    this.error,
  });

  final SiteStatus status;

  /// Site persisté, ou `null` si jamais réglé — un état nominal, pas une
  /// erreur : l'alignement le demandera au premier besoin.
  final ObservingSite? site;

  final String? error;

  SiteState copyWith({
    SiteStatus? status,
    ObservingSite? site,
    Object? error = _sentinel,
  }) =>
      SiteState(
        status: status ?? this.status,
        site: site ?? this.site,
        error: identical(error, _sentinel) ? this.error : error as String?,
      );

  @override
  List<Object?> get props => [status, site?.lat, site?.lon, site?.setAt, error];
}

const _sentinel = Object();
