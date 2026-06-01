import 'package:bloc_concurrency/bloc_concurrency.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:stream_transform/stream_transform.dart';

import 'catalogue_event.dart';
import 'catalogue_repository.dart';
import 'catalogue_state.dart';

const _debounce = Duration(milliseconds: 300);

EventTransformer<E> _debounced<E>() =>
    (events, mapper) => droppable<E>()(events.debounce(_debounce), mapper);

/// Bloc de la page Catalogue : liste/recherche/filtres + déclenchement GoTo.
/// Les statuts transverses (is_aligned, goto_in_progress, fix GPS) viennent
/// de l'AppBloc/SSE — pas d'ici.
class CatalogueBloc extends Bloc<CatalogueEvent, CatalogueState> {
  CatalogueBloc({required this.repo})
      : super(const CatalogueLoading(CatalogueFilters())) {
    on<CatalogueOpened>(_onReload);
    on<SearchChanged>(_onSearch, transformer: _debounced());
    on<MagFilterChanged>(_onMag);
    on<VisibleNowToggled>(_onVisible);
    on<GoToRequested>(_onGoTo);
    on<AbortRequested>(_onAbort);
  }

  final CatalogueRepository repo;

  CatalogueFilters get _filters => switch (state) {
        CatalogueLoading(:final filters) => filters,
        CatalogueLoaded(:final filters) => filters,
        CatalogueError(:final filters) => filters,
      };

  Future<void> _query(
      Emitter<CatalogueState> emit, CatalogueFilters filters) async {
    emit(CatalogueLoading(filters));
    try {
      final objects = await repo.listObjects(
        search: filters.search,
        maxMag: filters.maxMag,
        visibleNow: filters.visibleNow,
      );
      emit(CatalogueLoaded(objects: objects, filters: filters));
    } catch (e) {
      emit(CatalogueError(e.toString(), filters));
    }
  }

  Future<void> _onReload(CatalogueOpened e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters);

  Future<void> _onSearch(SearchChanged e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters.copyWith(search: e.text));

  Future<void> _onMag(MagFilterChanged e, Emitter<CatalogueState> emit) =>
      _query(
          emit,
          e.maxMag == null
              ? _filters.copyWith(clearMaxMag: true)
              : _filters.copyWith(maxMag: e.maxMag));

  Future<void> _onVisible(VisibleNowToggled e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters.copyWith(visibleNow: e.enabled));

  Future<void> _onGoTo(GoToRequested e, Emitter<CatalogueState> emit) async {
    try {
      await repo.goto(e.raDeg, e.decDeg, e.targetName);
    } catch (err) {
      emit(CatalogueError(err.toString(), _filters));
    }
  }

  Future<void> _onAbort(AbortRequested e, Emitter<CatalogueState> emit) async {
    try {
      await repo.abort();
    } catch (err) {
      emit(CatalogueError(err.toString(), _filters));
    }
  }
}
