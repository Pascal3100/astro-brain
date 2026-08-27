import 'dart:convert';

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

  // -------------------------------------------------------------------------
  // Helpers JSON génériques
  // -------------------------------------------------------------------------

  group('ApiService.getJsonOrNull', () {
    test('GET dont le corps est le littéral null retourne null', () async {
      // C'est le contrat de `GET /site` tant qu'aucun site n'est réglé :
      // 200 + `null`, que `getJson` ne saurait pas décoder.
      final client = MockClient((req) async {
        expect(req.url.path, '/site');
        return http.Response('null', 200,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      expect(await api.getJsonOrNull('/site'), isNull);
    });

    test('GET avec un objet retourne la map décodée', () async {
      final client = MockClient(
        (_) async => http.Response('{"lat": 43.6, "lon": 1.44}', 200,
            headers: {'content-type': 'application/json'}),
      );
      final api = ApiService(host: host, client: client);
      expect((await api.getJsonOrNull('/site'))!['lat'], 43.6);
    });
  });

  group('ApiService.putJson', () {
    test('PUT /site envoie le corps et accepte un 204', () async {
      String? sent;
      final client = MockClient((req) async {
        expect(req.method, 'PUT');
        expect(req.url.path, '/site');
        sent = req.body;
        return http.Response('', 204);
      });
      final api = ApiService(host: host, client: client);
      await api.putJson('/site', {'lat': 43.6, 'lon': 1.44});
      expect(jsonDecode(sent!), {'lat': 43.6, 'lon': 1.44});
    });

    test('jette ApiException sur un status refusé', () async {
      final client = MockClient(
        (_) async => http.Response('{"detail": "hors bornes"}', 422,
            headers: {'content-type': 'application/json'}),
      );
      final api = ApiService(host: host, client: client);
      expect(
        api.putJson('/site', {'lat': 91.0, 'lon': 1.44}),
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

const _snapshot = '''
{
  "overall": "green",
  "subsystems": {
    "mount": {"state": "ready", "details": {}, "since": "2026-04-17T20:31:12Z", "message": null},
    "tracking": {"state": "sidereal", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "network": {"state": "client", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null},
    "system": {"state": "ok", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null}
  },
  "seq": 142,
  "ts": "2026-04-17T20:31:12Z"
}
''';
