import 'package:equatable/equatable.dart';

/// Événements de la page Catalogue (liste/filtres + GoTo/abort).
sealed class CatalogueEvent extends Equatable {
  const CatalogueEvent();
  @override
  List<Object?> get props => [];
}

class CatalogueOpened extends CatalogueEvent {
  const CatalogueOpened();
}

class SearchChanged extends CatalogueEvent {
  const SearchChanged(this.text);
  final String text;
  @override
  List<Object?> get props => [text];
}

class MagFilterChanged extends CatalogueEvent {
  const MagFilterChanged(this.maxMag);
  final double? maxMag;
  @override
  List<Object?> get props => [maxMag];
}

class VisibleNowToggled extends CatalogueEvent {
  const VisibleNowToggled(this.enabled);
  final bool enabled;
  @override
  List<Object?> get props => [enabled];
}

/// Filtre par constellation (abréviation IAU, `null` = toutes). Appliqué
/// côté app sur la liste déjà chargée — pas de requête backend.
class ConstellationChanged extends CatalogueEvent {
  const ConstellationChanged(this.constellation);
  final String? constellation;
  @override
  List<Object?> get props => [constellation];
}

class KindFilterChanged extends CatalogueEvent {
  const KindFilterChanged(this.kind);
  final String? kind;
  @override
  List<Object?> get props => [kind];
}

class GoToRequested extends CatalogueEvent {
  const GoToRequested(this.id, {this.confirmSolar = false});
  final String id;
  final bool confirmSolar;
  @override
  List<Object?> get props => [id, confirmSolar];
}

class AbortRequested extends CatalogueEvent {
  const AbortRequested();
}
