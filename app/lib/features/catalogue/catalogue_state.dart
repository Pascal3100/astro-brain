import 'package:equatable/equatable.dart';

import 'catalogue_models.dart';

/// Résultat transitoire (one-shot) d'un GoTo, consommé par un BlocListener.
sealed class GotoOutcome extends Equatable {
  const GotoOutcome();
  @override
  List<Object?> get props => [];
}

/// GoTo rejeté : message FR à afficher (SnackBar). N'efface pas la liste.
class GotoError extends GotoOutcome {
  const GotoError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Le backend exige un acquittement solaire (409 solar_ack_required) pour
/// l'objet [objectId]. Déclenche le dialogue d'avertissement (Task 4).
class GotoSolarAck extends GotoOutcome {
  const GotoSolarAck(this.objectId);
  final String objectId;
  @override
  List<Object?> get props => [objectId];
}

/// Filtres actifs de la page (recherche, magnitude max, visible maintenant,
/// constellation). [constellation] est l'abréviation IAU (ex. `CMa`), `null`
/// = toutes ; ce filtre est appliqué côté app (la liste est déjà chargée).
class CatalogueFilters extends Equatable {
  const CatalogueFilters({
    this.search = '',
    this.maxMag,
    this.visibleNow = true,
    this.constellation,
  });

  final String search;
  final double? maxMag;
  final bool visibleNow;
  final String? constellation;

  CatalogueFilters copyWith({
    String? search,
    double? maxMag,
    bool? visibleNow,
    String? constellation,
    bool clearMaxMag = false,
    bool clearConstellation = false,
  }) =>
      CatalogueFilters(
        search: search ?? this.search,
        maxMag: clearMaxMag ? null : (maxMag ?? this.maxMag),
        visibleNow: visibleNow ?? this.visibleNow,
        constellation:
            clearConstellation ? null : (constellation ?? this.constellation),
      );

  @override
  List<Object?> get props => [search, maxMag, visibleNow, constellation];
}

/// États de la page Catalogue.
sealed class CatalogueState extends Equatable {
  const CatalogueState();
  @override
  List<Object?> get props => [];
}

class CatalogueLoading extends CatalogueState {
  const CatalogueLoading(this.filters);
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [filters];
}

class CatalogueLoaded extends CatalogueState {
  const CatalogueLoaded({
    required this.objects,
    required this.filters,
    this.availableConstellations = const [],
    this.gotoOutcome,
  });

  /// Objets affichés (déjà filtrés par constellation côté app).
  final List<CatalogObjectDto> objects;
  final CatalogueFilters filters;

  /// Abréviations IAU des constellations présentes dans la liste chargée
  /// (avant filtre constellation), triées par nom complet — alimente le menu.
  final List<String> availableConstellations;

  /// Outcome transitoire d'un GoTo (SnackBar / dialogue), `null` au repos.
  final GotoOutcome? gotoOutcome;

  CatalogueLoaded copyWith({
    List<CatalogObjectDto>? objects,
    CatalogueFilters? filters,
    List<String>? availableConstellations,
    GotoOutcome? gotoOutcome,
    bool clearOutcome = false,
  }) =>
      CatalogueLoaded(
        objects: objects ?? this.objects,
        filters: filters ?? this.filters,
        availableConstellations:
            availableConstellations ?? this.availableConstellations,
        gotoOutcome: clearOutcome ? null : (gotoOutcome ?? this.gotoOutcome),
      );

  @override
  List<Object?> get props =>
      [objects, filters, availableConstellations, gotoOutcome];
}

class CatalogueError extends CatalogueState {
  const CatalogueError(this.message, this.filters);
  final String message;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [message, filters];
}
