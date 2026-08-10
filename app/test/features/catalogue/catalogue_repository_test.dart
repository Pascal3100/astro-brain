import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;
  setUp(() => api = _MockApi());

  test('listObjects passes query params (not embedded in path) and parses',
      () async {
    when(() => api.getJson(any(), query: any(named: 'query')))
        .thenAnswer((_) async => {
              'objects': [
                {
                  'qualified_id': 'star:vega', 'kind': 'star', 'name': 'Vega',
                  'ra_deg': 279.23, 'dec_deg': 38.78, 'mag': 0.0,
                  'altitude_deg': 18.0, 'azimuth_deg': 51.0,
                }
              ],
              'count': 1, 'limit': 500, 'offset': 0,
            });

    final repo = CatalogueRepository(api: api);
    final objs = await repo.listObjects(
        search: 'veg', maxMag: 3.0, visibleNow: true);

    expect(objs, hasLength(1));
    expect(objs.first.name, 'Vega');
    // Le path ne doit PAS contenir de query string (sinon `?` encodé → 404).
    final path = verify(() => api.getJson(captureAny(),
            query: captureAny(named: 'query')))
        .captured;
    expect(path[0], '/catalog/objects');
    final query = path[1] as Map<String, String>;
    expect(query['search'], 'veg');
    expect(query['max_mag'], '3.0');
    expect(query['visible_now'], 'true');
    expect(query['limit'], '500');
  });

  test('goto posts {id, confirm_solar}', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    final repo = CatalogueRepository(api: api);
    await repo.goto('star:sirius', confirmSolar: true);
    verify(() => api.postJson(
        '/goto', {'id': 'star:sirius', 'confirm_solar': true})).called(1);
  });

  test('goto défaut confirm_solar=false', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    final repo = CatalogueRepository(api: api);
    await repo.goto('planet:mars');
    verify(() => api.postJson(
        '/goto', {'id': 'planet:mars', 'confirm_solar': false})).called(1);
  });

  test('abort posts /stop', () async {
    when(() => api.stop()).thenAnswer((_) async {});
    final repo = CatalogueRepository(api: api);
    await repo.abort();
    verify(() => api.stop()).called(1);
  });
}
