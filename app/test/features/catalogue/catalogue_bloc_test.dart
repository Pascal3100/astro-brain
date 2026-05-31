import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_event.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements CatalogueRepository {}

CatalogObjectDto _vega() => const CatalogObjectDto(
      qualifiedId: 'star:vega',
      kind: 'star',
      name: 'Vega',
      raDeg: 279.23,
      decDeg: 38.78,
      mag: 0.0,
      altitudeDeg: 18.0,
    );

void main() {
  late _MockRepo repo;
  setUp(() => repo = _MockRepo());

  blocTest<CatalogueBloc, CatalogueState>(
    'CatalogueOpened → Loading → Loaded',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const CatalogueOpened()),
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>().having((s) => s.objects.length, 'count', 1),
    ],
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'VisibleNowToggled re-queries with flag',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const VisibleNowToggled(false)),
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>()
          .having((s) => s.filters.visibleNow, 'visibleNow', false),
    ],
    verify: (_) {
      verify(() => repo.listObjects(
          search: any(named: 'search'),
          maxMag: any(named: 'maxMag'),
          visibleNow: false)).called(1);
    },
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'GoToRequested calls repo.goto',
    build: () {
      when(() => repo.goto(any(), any(), any())).thenAnswer((_) async {});
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const GoToRequested(101.0, -16.0, 'Sirius')),
    verify: (_) => verify(() => repo.goto(101.0, -16.0, 'Sirius')).called(1),
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'CatalogueOpened error → CatalogueError',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenThrow(Exception('boom'));
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const CatalogueOpened()),
    expect: () => [isA<CatalogueLoading>(), isA<CatalogueError>()],
  );
}
