import 'package:equatable/equatable.dart';

import 'catalogue_models.dart';

/// Filtres actifs de la page (recherche, magnitude max, visible maintenant).
class CatalogueFilters extends Equatable {
  const CatalogueFilters({
    this.search = '',
    this.maxMag,
    this.visibleNow = true,
  });

  final String search;
  final double? maxMag;
  final bool visibleNow;

  CatalogueFilters copyWith({
    String? search,
    double? maxMag,
    bool? visibleNow,
    bool clearMaxMag = false,
  }) =>
      CatalogueFilters(
        search: search ?? this.search,
        maxMag: clearMaxMag ? null : (maxMag ?? this.maxMag),
        visibleNow: visibleNow ?? this.visibleNow,
      );

  @override
  List<Object?> get props => [search, maxMag, visibleNow];
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
  const CatalogueLoaded({required this.objects, required this.filters});
  final List<CatalogObjectDto> objects;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [objects, filters];
}

class CatalogueError extends CatalogueState {
  const CatalogueError(this.message, this.filters);
  final String message;
  final CatalogueFilters filters;
  @override
  List<Object?> get props => [message, filters];
}
