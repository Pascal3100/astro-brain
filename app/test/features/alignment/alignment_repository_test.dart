import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

Map<String, dynamic> _starJson(String id, String name) => {
      'id': id,
      'name': name,
      'ra': 10.0,
      'dec': 20.0,
      'mag': 1.5,
    };

Map<String, dynamic> _sessionJson({int currentIdx = 0}) => {
      'session_id': 'sess-1',
      'started_at_utc': '2026-05-10T20:00:00Z',
      'candidates': [_starJson('s1', 'Vega'), _starJson('s2', 'Deneb')],
      'selected': [_starJson('s1', 'Vega'), _starJson('s2', 'Deneb')],
      'records': [null, null, null],
      'current_idx': currentIdx,
    };

void main() {
  setUpAll(() {
    registerFallbackValue(<String, dynamic>{});
  });

  late _MockApi api;
  late AlignmentRepository repo;

  setUp(() {
    api = _MockApi();
    repo = AlignmentRepository(api: api);
  });

  group('AlignmentRepository.getSession', () {
    test('returns null when backend says null', () async {
      when(() => api.getJson('/align/session'))
          .thenAnswer((_) async => {'session': null});
      final session = await repo.getSession();
      expect(session, isNull);
    });

    test('parses session when backend returns one', () async {
      when(() => api.getJson('/align/session'))
          .thenAnswer((_) async => {'session': _sessionJson(currentIdx: 1)});
      final session = await repo.getSession();
      expect(session, isNotNull);
      expect(session!.sessionId, 'sess-1');
      expect(session.currentIdx, 1);
      expect(session.candidates, hasLength(2));
      expect(session.selected, hasLength(2));
      expect(session.records, hasLength(3));
      expect(session.records[0], isNull);
    });
  });

  group('AlignmentRepository.start', () {
    test('returns parsed session', () async {
      when(() => api.postJson('/align/start', any()))
          .thenAnswer((_) async => _sessionJson());
      final session = await repo.start(['s1', 's2', 's3']);
      expect(session.sessionId, 'sess-1');
      final captured = verify(() => api.postJson('/align/start', captureAny()))
          .captured
          .single as Map<String, dynamic>;
      expect(captured['star_ids'], ['s1', 's2', 's3']);
    });
  });

  group('AlignmentRepository.swap', () {
    test('sends idx in path and star body', () async {
      when(() => api.postJson('/align/swap/2', any()))
          .thenAnswer((_) async => _sessionJson(currentIdx: 2));
      final session = await repo.swap(2, 'sNew');
      expect(session.currentIdx, 2);
      final captured = verify(
        () => api.postJson('/align/swap/2', captureAny()),
      ).captured.single as Map<String, dynamic>;
      expect(captured['star_id'], 'sNew');
    });
  });

  group('AlignmentRepository.record', () {
    test('sends idx body', () async {
      when(() => api.postJson('/align/record', any()))
          .thenAnswer((_) async => _sessionJson(currentIdx: 1));
      final session = await repo.record(0);
      expect(session.currentIdx, 1);
      final captured = verify(
        () => api.postJson('/align/record', captureAny()),
      ).captured.single as Map<String, dynamic>;
      expect(captured['idx'], 0);
    });
  });

  group('AlignmentRepository.restartStar', () {
    test('sends idx body', () async {
      when(() => api.postJson('/align/restart_star', any()))
          .thenAnswer((_) async => _sessionJson(currentIdx: 1));
      final session = await repo.restartStar(1);
      expect(session.currentIdx, 1);
      final captured = verify(
        () => api.postJson('/align/restart_star', captureAny()),
      ).captured.single as Map<String, dynamic>;
      expect(captured['idx'], 1);
    });
  });

  group('AlignmentRepository.finalize', () {
    test('parses AlignmentModelDto', () async {
      when(() => api.postJson('/align/finalize', any())).thenAnswer(
        (_) async => {
          'rms_arcmin': 4.2,
          'residuals_arcmin': [3.0, 4.0, 5.5],
          'validated_at_utc': '2026-05-10T20:30:00Z',
          'quality': 'good',
          'star_ids': ['s1', 's2', 's3'],
        },
      );
      final model = await repo.finalize();
      expect(model.rmsArcmin, 4.2);
      expect(model.residualsArcmin, [3.0, 4.0, 5.5]);
      expect(model.validatedAtUtc, '2026-05-10T20:30:00Z');
      expect(model.quality, 'good');
      expect(model.starIds, ['s1', 's2', 's3']);
    });
  });

  group('AlignmentRepository.cancel', () {
    test("calls api.delete('/align/session')", () async {
      when(() => api.delete('/align/session')).thenAnswer((_) async {});
      await repo.cancel();
      verify(() => api.delete('/align/session')).called(1);
    });
  });
}
