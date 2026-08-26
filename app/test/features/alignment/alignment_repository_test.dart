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

  group('AlignmentRepository.fetchConstellation', () {
    test('calls getJson with path + query params, returns parsed dto', () async {
      when(
        () => api.getJson(any(), query: any(named: 'query')),
      ).thenAnswer(
        (_) async => {
          'abbr': 'UMa',
          'name': 'Ursa Major',
          'oriented': false,
          'nodes': [],
          'segments': [],
        },
      );

      final dto = await repo.fetchConstellation(
        'UMa',
        raDeg: 165.9,
        decDeg: 61.7,
      );

      expect(dto.abbr, 'UMa');
      expect(dto.name, 'Ursa Major');
      expect(dto.oriented, isFalse);
      expect(dto.nodes, isEmpty);
      expect(dto.segments, isEmpty);

      // Vérifie que le path ne contient PAS de query string (bug f179db4).
      final captured = verify(
        () => api.getJson(captureAny(), query: captureAny(named: 'query')),
      ).captured;
      expect(captured[0], '/align/constellation/UMa');
      final query = captured[1] as Map<String, String>;
      expect(query['target_ra'], '165.9');
      expect(query['target_dec'], '61.7');
    });
  });

  group('AlignmentRepository.fetchVisibleStars', () {
    test('parses constellations map into Map<abbr, List<StarDto>>', () async {
      when(
        () => api.getJson('/align/stars/visible'),
      ).thenAnswer(
        (_) async => {
          'constellations': {
            'UMa': [
              {
                'id': 'alkaid',
                'name': 'Alkaid',
                'bayer': 'η UMa',
                'ra_deg': 206.885,
                'dec_deg': 49.313,
                'mag': 1.86,
                'az': 42.0,
                'alt': 58.0,
              },
            ],
          },
        },
      );

      final map = await repo.fetchVisibleStars();

      expect(map.keys, contains('UMa'));
      expect(map['UMa'], hasLength(1));
      final star = map['UMa']!.first;
      expect(star.id, 'alkaid');
      expect(star.name, 'Alkaid');
      expect(star.bayer, 'η UMa');
      expect(star.raDeg, closeTo(206.885, 0.001));
      expect(star.decDeg, closeTo(49.313, 0.001));
      expect(star.mag, closeTo(1.86, 0.001));

      verify(() => api.getJson('/align/stars/visible')).called(1);
    });
  });

  group('AlignmentRepository.putSite', () {
    test('puts lat/lon to /site', () async {
      when(() => api.putJson(any(), any())).thenAnswer((_) async {});

      await repo.putSite(43.6, 1.44);

      final captured = verify(
        () => api.putJson(captureAny(), captureAny()),
      ).captured;
      expect(captured[0], '/site');
      final body = captured[1] as Map<String, dynamic>;
      expect(body['lat'], closeTo(43.6, 0.001));
      expect(body['lon'], closeTo(1.44, 0.001));
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
