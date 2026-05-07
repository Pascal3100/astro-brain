import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/calibration.dart';
import 'package:astro_brain/services/calibration_progress_stream.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

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
    '{"state":"sampling","samples_n":42,"coverage_pct":0.0,"sigma":0.07,'
    '"hint":"continue"}';

void main() {
  test('émet un CalibrationProgress par event progress', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CalibrationProgressStream(
      host: const PiHost(),
      sensorId: 'adxl345_mount',
      sessionId: 'abc123',
      clientFactory: () => client,
    );

    final progresses = <CalibrationProgress>[];
    final done = Completer<void>();
    svc.open().listen(progresses.add, onDone: done.complete);

    // Laisse le `then` du `client.send` se résoudre.
    await Future<void>.delayed(const Duration(milliseconds: 20));

    bytes.add(utf8.encode('event: progress\ndata: $_payload\n\n'));
    bytes.add(utf8.encode('event: progress\ndata: $_payload\n\n'));
    await Future<void>.delayed(const Duration(milliseconds: 20));

    expect(progresses, hasLength(2));
    expect(progresses.first.samplesN, 42);
    expect(progresses.first.sigma, closeTo(0.07, 1e-9));
    expect(progresses.first.hint, 'continue');

    // Backend envoie `event: end` → stream se ferme proprement.
    bytes.add(utf8.encode('event: end\ndata: {}\n\n'));
    await done.future.timeout(const Duration(seconds: 1));

    await bytes.close();
  });

  test('session_id passé en query param et path correct', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CalibrationProgressStream(
      host: const PiHost(),
      sensorId: 'lis3mdl',
      sessionId: 'deadbeef',
      clientFactory: () => client,
    );

    svc.open().listen((_) {});
    await Future<void>.delayed(const Duration(milliseconds: 20));

    expect(client.requests, hasLength(1));
    expect(client.requests.first.path, '/calibration/lis3mdl/stream');
    expect(client.requests.first.queryParameters['session_id'], 'deadbeef');

    await svc.cancel();
    await bytes.close();
  });

  test('cancel ferme prématurément le stream', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CalibrationProgressStream(
      host: const PiHost(),
      sensorId: 'adxl345_mount',
      sessionId: 's1',
      clientFactory: () => client,
    );

    final done = Completer<void>();
    svc.open().listen((_) {}, onDone: done.complete);
    await Future<void>.delayed(const Duration(milliseconds: 20));

    await svc.cancel();
    await done.future.timeout(const Duration(seconds: 1));

    await bytes.close();
  });

  test('réponse non-200 termine le stream sans émettre', () async {
    final client = _FakeClient([(409, const Stream<List<int>>.empty())]);
    final svc = CalibrationProgressStream(
      host: const PiHost(),
      sensorId: 'adxl345_mount',
      sessionId: 's1',
      clientFactory: () => client,
    );

    final progresses = <CalibrationProgress>[];
    final done = Completer<void>();
    svc.open().listen(progresses.add, onDone: done.complete);

    await done.future.timeout(const Duration(seconds: 1));
    expect(progresses, isEmpty);
  });

  test('open() appelé deux fois lève StateError', () async {
    final bytes = StreamController<List<int>>();
    final client = _FakeClient([(200, bytes.stream)]);
    final svc = CalibrationProgressStream(
      host: const PiHost(),
      sensorId: 'adxl345_mount',
      sessionId: 's1',
      clientFactory: () => client,
    );
    svc.open().listen((_) {});
    expect(() => svc.open(), throwsStateError);
    await svc.cancel();
    await bytes.close();
  });
}
