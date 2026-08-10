import 'package:astro_brain/features/catalogue/catalogue_bloc.dart';
import 'package:astro_brain/features/catalogue/catalogue_event.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/catalogue_state.dart';
import 'package:astro_brain/services/api_service.dart';
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

  blocTest<CatalogueBloc, CatalogueState>(
    'GoTo OK → aucun CatalogueError, liste préservée',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      when(() => repo.goto(any(), confirmSolar: any(named: 'confirmSolar')))
          .thenAnswer((_) async {});
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const GoToRequested('star:vega'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>(),
    ],
    verify: (_) => verify(
        () => repo.goto('star:vega', confirmSolar: false)).called(1),
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'GoTo not_aligned → GotoError, liste préservée',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      when(() => repo.goto(any(), confirmSolar: any(named: 'confirmSolar')))
          .thenThrow(ApiException('POST /goto failed',
              statusCode: 409, detail: 'not_aligned'));
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const GoToRequested('star:vega'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>().having((s) => s.gotoOutcome, 'outcome', isNull),
      isA<CatalogueLoaded>().having(
          (s) => (s.gotoOutcome as GotoError?)?.message,
          'msg',
          contains('non alignée')),
      isA<CatalogueLoaded>().having((s) => s.gotoOutcome, 'cleared', isNull),
    ],
  );

  CatalogObjectDto sirius() => const CatalogObjectDto(
        qualifiedId: 'star:sirius',
        kind: 'star',
        name: 'Sirius',
        raDeg: 101.0,
        decDeg: -16.0,
        mag: -1.45,
        constellation: 'CMa',
      );

  CatalogObjectDto vegaLyr() => const CatalogObjectDto(
        qualifiedId: 'star:vega',
        kind: 'star',
        name: 'Vega',
        raDeg: 279.23,
        decDeg: 38.78,
        mag: 0.0,
        constellation: 'Lyr',
      );

  blocTest<CatalogueBloc, CatalogueState>(
    'Loaded exposes available constellations (sorted by full name)',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [sirius(), vegaLyr()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const CatalogueOpened()),
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>()
          // "Grand Chien" (CMa) avant "Lyre" (Lyr) en tri par nom complet.
          .having((s) => s.availableConstellations, 'constellations',
              ['CMa', 'Lyr'])
          .having((s) => s.objects.length, 'count', 2),
    ],
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'ConstellationChanged filters client-side without re-querying',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [sirius(), vegaLyr()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const ConstellationChanged('CMa'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>().having((s) => s.objects.length, 'all', 2),
      isA<CatalogueLoaded>()
          .having((s) => s.objects.length, 'filtered', 1)
          .having((s) => s.objects.first.name, 'name', 'Sirius')
          .having((s) => s.filters.constellation, 'sel', 'CMa'),
    ],
    verify: (_) {
      // Un seul appel backend : le filtre constellation est client-side.
      verify(() => repo.listObjects(
          search: any(named: 'search'),
          maxMag: any(named: 'maxMag'),
          visibleNow: any(named: 'visibleNow'))).called(1);
    },
  );
}
