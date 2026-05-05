import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/sensor_readings.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:astro_brain/services/tilt_stream_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

/// Fake client qui rejoue une liste de réponses, une par appel à [send].
/// Capture chaque [Uri] requise dans [requests] pour assertions.
class _FakeClient extends http.BaseClient {
  _FakeClient(this.responses);

  /// File de réponses : chaque entrée est un (statusCode, bodyStream).
  final List<(int, Stream<List<int>>)> responses;
  final List<Uri> requests = [];
  int _index = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    requests.add(request.url);
    final (status, stream) = responses[_index++];
    return http.StreamedResponse(
      stream,
      status,
      headers: {'content-type': 'text/event-stream'},
    );
  }
}

const _payload =
    '{"ts":"2026-05-05T12:00:00Z","pitch_deg":1.23,"roll_deg":-0.45,'
    '"magnitude_g":1.001,"calibrated":true}';

void main() {
  test('parse un event tilt et émet un TiltReading', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = TiltStreamService(
      host: const PiHost(),
      hz: 5,
      clientFactory: () => client,
    );

    final first = svc.stream.first;
    svc.start();

    bytes.add(utf8.encode('event: tilt\ndata: $_payload\n\n'));

    final reading = await first.timeout(const Duration(seconds: 2));
    expect(reading.pitchDeg, closeTo(1.23, 1e-9));
    expect(reading.rollDeg, closeTo(-0.45, 1e-9));
    expect(reading.magnitudeG, closeTo(1.001, 1e-9));
    expect(reading.calibrated, isTrue);
    expect(reading.ts, DateTime.parse('2026-05-05T12:00:00Z'));

    await svc.stop();
    await bytes.close();
  });

  test("hz est répercuté dans l'URI de la requête", () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = TiltStreamService(
      host: const PiHost(),
      hz: 7,
      clientFactory: () => client,
    );

    svc.start();
    // Laisse le `then` du `client.send` se résoudre.
    await Future<void>.delayed(const Duration(milliseconds: 20));

    expect(client.requests, hasLength(1));
    expect(client.requests.first.path, '/sensors/tilt/stream');
    expect(client.requests.first.queryParameters['hz'], '7');

    await svc.stop();
    await bytes.close();
  });

  test('reconnect après une réponse 500 (back-off ~1s)', () async {
    final bytes2 = StreamController<List<int>>();
    final client = _FakeClient([
      (500, const Stream<List<int>>.empty()),
      (200, bytes2.stream),
    ]);
    final svc = TiltStreamService(
      host: const PiHost(),
      clientFactory: () => client,
    );

    final readings = <TiltReading>[];
    final sub = svc.stream.listen(readings.add);
    svc.start();

    // Attend la reconnexion (back-off[0] = 1s) + un peu de marge.
    await Future<void>.delayed(const Duration(milliseconds: 1300));

    expect(client.requests.length, greaterThanOrEqualTo(2));

    bytes2.add(utf8.encode('event: tilt\ndata: $_payload\n\n'));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(readings, hasLength(1));
    expect(readings.first.pitchDeg, closeTo(1.23, 1e-9));

    await sub.cancel();
    await svc.stop();
    await bytes2.close();
  });

  test('ignore les events autres que tilt', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = TiltStreamService(
      host: const PiHost(),
      clientFactory: () => client,
    );

    final readings = <TiltReading>[];
    final sub = svc.stream.listen(readings.add);
    svc.start();

    // Event d'un autre type → doit être ignoré, pas de crash.
    bytes.add(utf8.encode('event: ping\ndata: {}\n\n'));
    bytes.add(utf8.encode('event: tilt\ndata: $_payload\n\n'));

    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(readings, hasLength(1));

    await sub.cancel();
    await svc.stop();
    await bytes.close();
  });
}
