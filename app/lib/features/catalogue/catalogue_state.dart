import 'package:equatable/equatable.dart';

import 'catalogue_models.dart';

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
  });

  /// Objets affichés (déjà filtrés par constellation côté app).
  final List<CatalogObjectDto> objects;
  final CatalogueFilters filters;

  /// Abréviations IAU des constellations présentes dans la liste chargée
  /// (avant filtre constellation), triées par nom complet — alimente le menu.
  final List<String> availableConstellations;

  @override
  List<Object?> get props => [objects, filters, availableConstellations];
}

class CatalogueError extends CatalogueState {
  const CatalogueError(this.message, this.filters);
  final String message;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [message, filters];
}
