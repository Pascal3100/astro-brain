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

class GoToRequested extends CatalogueEvent {
  const GoToRequested(this.raDeg, this.decDeg, this.targetName);
  final double raDeg;
  final double decDeg;
  final String targetName;
  @override
  List<Object?> get props => [raDeg, decDeg, targetName];
}

class AbortRequested extends CatalogueEvent {
  const AbortRequested();
}
