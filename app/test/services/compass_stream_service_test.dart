import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/sensor_readings.dart';
import 'package:astro_brain/services/compass_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

/// Fake client qui rejoue une liste de réponses, une par appel à [send].
class _FakeClient extends http.BaseClient {
  _FakeClient(this.responses);

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
    '{"ts":"2026-05-05T12:00:00Z","heading_deg":142.7,'
    '"magnitude_uT":48.3,"raw":{"x":12.5,"y":-3.1,"z":48.0},'
    '"tilt_compensated":true,"calibrated":true}';

void main() {
  test('parse un event compass et émet un CompassReading', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CompassStreamService(
      host: const PiHost(),
      hz: 5,
      clientFactory: () => client,
    );

    final first = svc.stream.first;
    svc.start();

    bytes.add(utf8.encode('event: compass\ndata: $_payload\n\n'));

    final reading = await first.timeout(const Duration(seconds: 2));
    expect(reading.headingDeg, closeTo(142.7, 1e-9));
    expect(reading.magnitudeUt, closeTo(48.3, 1e-9));
    expect(reading.raw.$1, closeTo(12.5, 1e-9));
    expect(reading.raw.$2, closeTo(-3.1, 1e-9));
    expect(reading.raw.$3, closeTo(48.0, 1e-9));
    expect(reading.tiltCompensated, isTrue);
    expect(reading.calibrated, isTrue);
    expect(reading.ts, DateTime.parse('2026-05-05T12:00:00Z'));

    await svc.stop();
    await bytes.close();
  });

  test("hz est répercuté dans l'URI de la requête", () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CompassStreamService(
      host: const PiHost(),
      hz: 3,
      clientFactory: () => client,
    );

    svc.start();
    await Future<void>.delayed(const Duration(milliseconds: 20));

    expect(client.requests, hasLength(1));
    expect(client.requests.first.path, '/sensors/compass/stream');
    expect(client.requests.first.queryParameters['hz'], '3');

    await svc.stop();
    await bytes.close();
  });

  test('reconnect après une réponse 500 (back-off ~1s)', () async {
    final bytes2 = StreamController<List<int>>();
    final client = _FakeClient([
      (500, const Stream<List<int>>.empty()),
      (200, bytes2.stream),
    ]);
    final svc = CompassStreamService(
      host: const PiHost(),
      clientFactory: () => client,
    );

    final readings = <CompassReading>[];
    final sub = svc.stream.listen(readings.add);
    svc.start();

    await Future<void>.delayed(const Duration(milliseconds: 1300));

    expect(client.requests.length, greaterThanOrEqualTo(2));

    bytes2.add(utf8.encode('event: compass\ndata: $_payload\n\n'));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(readings, hasLength(1));
    expect(readings.first.headingDeg, closeTo(142.7, 1e-9));

    await sub.cancel();
    await svc.stop();
    await bytes2.close();
  });

  test('ignore les events autres que compass', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CompassStreamService(
      host: const PiHost(),
      clientFactory: () => client,
    );

    final readings = <CompassReading>[];
    final sub = svc.stream.listen(readings.add);
    svc.start();

    bytes.add(utf8.encode('event: tilt\ndata: {}\n\n'));
    bytes.add(utf8.encode('event: compass\ndata: $_payload\n\n'));

    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(readings, hasLength(1));

    await sub.cancel();
    await svc.stop();
    await bytes.close();
  });
}
