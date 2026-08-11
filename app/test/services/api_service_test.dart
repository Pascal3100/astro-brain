import 'dart:convert';

import 'package:astro_brain/models/calibration.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const host = PiHost(host: 'astro-brain.local', port: 8000);

  group('ApiService.fetchState', () {
    test('GET /state renvoie un SystemState parsé', () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/state');
        return http.Response(_snapshot, 200,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      final state = await api.fetchState();
      expect(state.seq, 142);
    });

    test('jette ApiException sur status != 200', () async {
      final client = MockClient(
          (_) async => http.Response('oops', 500));
      final api = ApiService(host: host, client: client);
      expect(api.fetchState(), throwsA(isA<ApiException>()));
    });
  });

  group('ApiService.slew', () {
    test('POST /slew avec body JSON correct', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        expect(req.url.path, '/slew');
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.slew(axis: Axis.alt, direction: Direction.plus, rate: 5);
      expect(captured, {'axis': 'alt', 'direction': '+', 'rate': 5});
    });
  });

  group('ApiService.stop', () {
    test('POST /stop sans axis envoie body vide', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.stop();
      expect(captured, <String, dynamic>{});
    });

    test('POST /stop avec axis envoie le champ', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.stop(axis: Axis.az);
      expect(captured, {'axis': 'az'});
    });
  });

  group('ApiService.setTracking', () {
    test('POST /tracking { enabled: true }', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.setTracking(true);
      expect(captured, {'enabled': true});
    });
  });

  // -------------------------------------------------------------------------
  // Calibration endpoints
  // -------------------------------------------------------------------------

  group('ApiService.getCalibrationStatus', () {
    test('GET /calibration/:id retourne un CalibrationStatus parsé', () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/calibration/lis3mdl');
        return http.Response(_calibrationStatusLisJson, 200,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      final status = await api.getCalibrationStatus('lis3mdl');
      expect(status.sensorId, 'lis3mdl');
      expect(status.payload, isA<Lis3mdlOffsets>());
    });

    test('jette ApiException sur status != 200', () async {
      final client = MockClient((_) async => http.Response('not found', 400));
      final api = ApiService(host: host, client: client);
      expect(
        api.getCalibrationStatus('lis3mdl'),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiService.startCalibration', () {
    test('POST /calibration/:id/start retourne session_id (202)', () async {
      final client = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/calibration/lis3mdl/start');
        return http.Response('{"session_id": "abc123"}', 202,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      final sessionId = await api.startCalibration('lis3mdl');
      expect(sessionId, 'abc123');
    });

    test('jette ApiException sur status != 202', () async {
      final client = MockClient((_) async => http.Response('conflict', 409));
      final api = ApiService(host: host, client: client);
      expect(
        api.startCalibration('lis3mdl'),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiService.finalizeCalibration', () {
    test('POST /calibration/:id/finalize retourne CalibrationStatus (200)',
        () async {
      final client = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/calibration/lis3mdl/finalize');
        return http.Response(_calibrationStatusLisJson, 200,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      final status = await api.finalizeCalibration('lis3mdl');
      expect(status.sensorId, 'lis3mdl');
      expect(status.payload, isA<Lis3mdlOffsets>());
    });

    test('jette ApiException sur status != 200', () async {
      final client = MockClient((_) async => http.Response('no session', 404));
      final api = ApiService(host: host, client: client);
      expect(
        api.finalizeCalibration('lis3mdl'),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiService.abortCalibration', () {
    test('POST /calibration/:id/abort réussit (200)', () async {
      final client = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/calibration/lis3mdl/abort');
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      // Doit compléter sans exception.
      await api.abortCalibration('lis3mdl');
    });

    test('jette ApiException sur status != 200', () async {
      final client = MockClient((_) async => http.Response('error', 500));
      final api = ApiService(host: host, client: client);
      expect(
        api.abortCalibration('lis3mdl'),
        throwsA(isA<ApiException>()),
      );
    });
  });

  group('ApiException.detail', () {
    test('postJson non-200 avec {"detail": x} peuple detail', () async {
      final client = MockClient(
        (_) async => http.Response('{"detail": "solar_ack_required"}', 409,
            headers: {'content-type': 'application/json'}),
      );
      final api = ApiService(host: host, client: client);
      try {
        await api.postJson('/goto', {'id': 'sun', 'confirm_solar': false});
        fail('devait jeter');
      } on ApiException catch (e) {
        expect(e.statusCode, 409);
        expect(e.detail, 'solar_ack_required');
      }
    });

    test('corps non-JSON → detail null', () async {
      final client = MockClient((_) async => http.Response('oops', 500));
      final api = ApiService(host: host, client: client);
      try {
        await api.getJson('/catalog/objects');
        fail('devait jeter');
      } on ApiException catch (e) {
        expect(e.detail, isNull);
        expect(e.statusCode, 500);
      }
    });
  });
}

const _calibrationStatusLisJson = '''
{
  "sensor_id": "lis3mdl",
  "calibrated_at": "2026-05-05T22:00:00+00:00",
  "payload": {
    "offsets": [10.0, -5.0, 3.0],
    "scale_matrix": [
      [1.02, 0.0, 0.0],
      [0.0, 0.98, 0.0],
      [0.0, 0.0, 1.05]
    ],
    "coverage_pct": 87.5,
    "residual": 0.012
  }
}
''';

const _snapshot = '''
{
  "overall": "green",
  "subsystems": {
    "mount": {"state": "ready", "details": {}, "since": "2026-04-17T20:31:12Z", "message": null},
    "gps": {"state": "fix_3d", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "tracking": {"state": "sidereal", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "network": {"state": "client", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null},
    "system": {"state": "ok", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null}
  },
  "seq": 142,
  "ts": "2026-04-17T20:31:12Z"
}
''';
