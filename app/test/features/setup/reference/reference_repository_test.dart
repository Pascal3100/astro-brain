import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;
  setUp(() => api = _MockApi());

  test('getStatus parse ready + fenêtre', () async {
    when(() => api.getJson(any())).thenAnswer((_) async => {
          'ready': true,
          'schema_version': 2,
          'generated_at': '2026-08-01T00:00:00+00:00',
          'window_start': '2026-08-01',
          'window_end': '2026-09-30',
        });
    final repo = ReferenceRepository(api: api);
    final s = await repo.getStatus();
    expect(s.ready, isTrue);
    expect(s.schemaVersion, 2);
    expect(s.windowEnd, '2026-09-30');
    verify(() => api.getJson('/reference/status')).called(1);
  });

  test('getStatus ready:false minimal', () async {
    when(() => api.getJson(any())).thenAnswer((_) async => {'ready': false});
    final repo = ReferenceRepository(api: api);
    final s = await repo.getStatus();
    expect(s.ready, isFalse);
    expect(s.generatedAt, isNull);
  });

  test('sync parse status', () async {
    when(() => api.postJson(any(), any()))
        .thenAnswer((_) async => {'status': 'updated', 'schema_version': 2});
    final repo = ReferenceRepository(api: api);
    final r = await repo.sync();
    expect(r.status, 'updated');
    verify(() => api.postJson('/reference/sync', const {})).called(1);
  });
}
