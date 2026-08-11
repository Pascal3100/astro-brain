import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_catalogue.dart';
import 'package:astro_brain/features/catalogue/local/visibility.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}
class _MockCatalogue extends Mock implements LocalCatalogue {}
class _MockVisibility extends Mock implements Visibility {}

void main() {
  late _MockApi api;
  late _MockCatalogue catalogue;
  late _MockVisibility visibility;
  setUp(() {
    api = _MockApi();
    catalogue = _MockCatalogue();
    visibility = _MockVisibility();
    registerFallbackValue(const LocalCatalogFilter());
  });

  CatalogueRepository repo() => CatalogueRepository(
      api: api, catalogue: catalogue, visibility: visibility);

  const vega = CatalogObjectDto(qualifiedId: 'star:vega', kind: 'star',
      name: 'Vega', raDeg: 279.23, decDeg: 38.78, mag: 0.0);

  test('listObjects lit le moteur local (pas /catalog/objects) et enrichit', () async {
    when(() => catalogue.listAll(any())).thenReturn([vega]);
    when(() => visibility.enrich(any(), visibleNow: any(named: 'visibleNow')))
        .thenAnswer((_) async => [vega.copyWith(altitudeDeg: 18.0)]);
    final out = await repo().listObjects(
        search: 'veg', maxMag: 3.0, visibleNow: true, kind: 'star', messier: false);
    expect(out.single.altitudeDeg, 18.0);
    // aucun appel réseau catalogue
    verifyNever(() => api.getJson(any(), query: any(named: 'query')));
    // le filtre local a bien reçu les critères
    final f = verify(() => catalogue.listAll(captureAny())).captured.single
        as LocalCatalogFilter;
    expect(f.kind, 'star');
    expect(f.search, 'veg');
    expect(f.maxMag, 3.0);
    expect(f.limit, 500);
    verify(() => visibility.enrich(any(), visibleNow: true)).called(1);
  });

  test('goto poste {id, confirm_solar} au Pi', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    await repo().goto('star:sirius', confirmSolar: true);
    verify(() => api.postJson('/goto', {'id': 'star:sirius', 'confirm_solar': true}))
        .called(1);
  });

  test('abort poste /stop', () async {
    when(() => api.stop()).thenAnswer((_) async {});
    await repo().abort();
    verify(() => api.stop()).called(1);
  });
}
