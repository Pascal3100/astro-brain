import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

Map<String, dynamic> _starJson(String id, String name) => {
  'id': id,
  'name': name,
  'bayer': '-',
  'ra_deg': 10.0,
  'dec_deg': 20.0,
  'mag': 1.5,
};

Map<String, dynamic> _sessionJson({int currentIdx = 0}) => {
  'session_id': 'sess-1',
  'candidates': [_starJson('s1', 'Vega'), _starJson('s2', 'Deneb')],
  'recorded_stars': [],
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
      when(
        () => api.getJson('/align/session'),
      ).thenAnswer((_) async => {'session': null});
      final session = await repo.getSession();
      expect(session, isNull);
    });

    test('parses session when backend returns one', () async {
      when(
        () => api.getJson('/align/session'),
      ).thenAnswer((_) async => {'session': _sessionJson(currentIdx: 1)});
      final session = await repo.getSession();
      expect(session, isNotNull);
      expect(session!.sessionId, 'sess-1');
      expect(session.currentIdx, 1);
      expect(session.candidates, hasLength(2));
      expect(session.recordedStars, isEmpty);
    });
  });

  group('AlignmentRepository.start', () {
    test('returns parsed session and posts empty body', () async {
      when(
        () => api.postJson('/align/start', any()),
      ).thenAnswer((_) async => _sessionJson());
      final session = await repo.start();
      expect(session.sessionId, 'sess-1');
      final captured =
          verify(
                () => api.postJson('/align/start', captureAny()),
              ).captured.single
              as Map<String, dynamic>;
      expect(captured, isEmpty);
    });
  });

  group('AlignmentRepository.swap', () {
    test('sends idx in path and star body', () async {
      when(
        () => api.postJson('/align/swap/2', any()),
      ).thenAnswer((_) async => _sessionJson(currentIdx: 2));
      const star = StarDto(
        id: 'sNew',
        name: 'Altair',
        bayer: 'α Aql',
        raDeg: 297.7,
        decDeg: 8.9,
        mag: 0.77,
      );
      final session = await repo.swap(2, star);
      expect(session.currentIdx, 2);
      final captured =
          verify(
                () => api.postJson('/align/swap/2', captureAny()),
              ).captured.single
              as Map<String, dynamic>;
      expect(captured['star'], isA<Map<String, dynamic>>());
      final starBody = captured['star'] as Map<String, dynamic>;
      expect(starBody['id'], 'sNew');
      expect(starBody['name'], 'Altair');
      expect(starBody['bayer'], 'α Aql');
      expect(starBody['ra_deg'], 297.7);
      expect(starBody['dec_deg'], 8.9);
      expect(starBody['mag'], 0.77);
    });
  });

  group('AlignmentRepository.record', () {
    test('sends idx body', () async {
      when(
        () => api.postJson('/align/record', any()),
      ).thenAnswer((_) async => _sessionJson(currentIdx: 1));
      final session = await repo.record(0);
      expect(session.currentIdx, 1);
      final captured =
          verify(
                () => api.postJson('/align/record', captureAny()),
              ).captured.single
              as Map<String, dynamic>;
      expect(captured['idx'], 0);
    });
  });

  group('AlignmentRepository.restartStar', () {
    test('sends idx body', () async {
      when(
        () => api.postJson('/align/restart_star', any()),
      ).thenAnswer((_) async => _sessionJson(currentIdx: 1));
      final session = await repo.restartStar(1);
      expect(session.currentIdx, 1);
      final captured =
          verify(
                () => api.postJson('/align/restart_star', captureAny()),
              ).captured.single
              as Map<String, dynamic>;
      expect(captured['idx'], 1);
    });
  });

  group('AlignmentRepository.finalize', () {
    test('parses AlignmentModelDto', () async {
      when(() => api.postJson('/align/finalize', any())).thenAnswer(
        (_) async => {
          'recorded_stars': [
            {
              'star_id': 's1',
              'sky_az': 1.0,
              'sky_alt': 2.0,
              'mount_az': 1.1,
              'mount_alt': 2.1,
            },
          ],
          'rms_arcmin': 4.2,
          'residuals': {'a': 1.2, 'b': 0.4, 'c': 0.5},
          'validated_at_utc': '2026-05-10T20:30:00Z',
          'quality': 'good',
        },
      );
      final model = await repo.finalize();
      expect(model.rmsArcmin, 4.2);
      expect(model.residuals, {'a': 1.2, 'b': 0.4, 'c': 0.5});
      expect(model.validatedAtUtc, '2026-05-10T20:30:00Z');
      expect(model.quality, 'good');
      expect(model.recordedStars, hasLength(1));
      expect(model.recordedStars.first.starId, 's1');
    });
  });

  group('AlignmentRepository.cancel', () {
    test("calls api.delete('/align/session')", () async {
      when(() => api.delete('/align/session')).thenAnswer((_) async {});
      await repo.cancel();
      verify(() => api.delete('/align/session')).called(1);
    });
  });

  group('AlignmentModelDto.outlierId', () {
    test('returns null when residuals are roughly equal', () {
      const model = AlignmentModelDto(
        recordedStars: [],
        rmsArcmin: 1.0,
        residuals: {'s1': 1.0, 's2': 1.1, 's3': 0.9},
        validatedAtUtc: '2026-05-10T20:30:00Z',
        quality: 'good',
      );
      expect(model.outlierId, isNull);
    });

    test('returns the worst-key when one residual is dramatically larger', () {
      const model = AlignmentModelDto(
        recordedStars: [],
        rmsArcmin: 5.0,
        residuals: {'s1': 0.5, 's2': 0.6, 's3': 10.0},
        validatedAtUtc: '2026-05-10T20:30:00Z',
        quality: 'poor',
      );
      expect(model.outlierId, 's3');
    });
  });
}
