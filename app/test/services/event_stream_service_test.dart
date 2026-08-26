import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/overall_status.dart';
import 'package:astro_brain/models/subsystem_states.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

class _FakeClient extends http.BaseClient {
  _FakeClient(this.controller);
  final StreamController<List<int>> controller;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return http.StreamedResponse(
      controller.stream,
      200,
      headers: {'content-type': 'text/event-stream'},
    );
  }
}

class _FailingClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    throw const SocketLikeException();
  }
}

class SocketLikeException implements Exception {
  const SocketLikeException();
}

const _snapshot = '''
{"overall":"green","subsystems":{"mount":{"state":"ready","details":{},"since":"2026-04-17T20:31:12Z","message":null},"tracking":{"state":"off","details":{},"since":"2026-04-17T20:30:00Z","message":null},"network":{"state":"client","details":{},"since":"2026-04-17T20:29:00Z","message":null},"system":{"state":"ok","details":{},"since":"2026-04-17T20:29:00Z","message":null}},"seq":1,"ts":"2026-04-17T20:31:12Z"}
''';

void main() {
  test('le snapshot initial est émis comme SystemState', () async {
    final bytes = StreamController<List<int>>();
    final svc = EventStreamService(
      host: const PiHost(),
      clientFactory: () => _FakeClient(bytes),
    );

    final first = svc.stream.first;
    svc.start();

    bytes.add(utf8.encode('event: snapshot\ndata: $_snapshot\n\n'));

    final state = await first.timeout(const Duration(seconds: 2));
    expect(state.seq, 1);
    expect(state.mount.state, MountState.ready);

    await svc.stop();
    await bytes.close();
  });

  test('un event update applique le changement sur le snapshot courant',
      () async {
    final bytes = StreamController<List<int>>();
    final svc = EventStreamService(
      host: const PiHost(),
      clientFactory: () => _FakeClient(bytes),
    );

    final states = <SystemState>[];
    final sub = svc.stream.listen(states.add);
    svc.start();

    bytes.add(utf8.encode('event: snapshot\ndata: $_snapshot\n\n'));
    bytes.add(utf8.encode(
        'event: update\ndata: {"subsystem":"tracking","state":{"state":"sidereal","details":{},"since":"2026-04-17T20:32:00Z","message":null},"overall":"orange","seq":2,"ts":"2026-04-17T20:32:00Z"}\n\n'));

    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(states.length, 2);
    expect(states[1].tracking.state, TrackingState.sidereal);
    expect(states[1].overall, OverallStatus.orange);

    await sub.cancel();
    await svc.stop();
    await bytes.close();
  });

  test('une erreur de connexion est propagée au stream avant reconnect',
      () async {
    final svc = EventStreamService(
      host: const PiHost(),
      clientFactory: _FailingClient.new,
    );

    final errors = <Object>[];
    final sub = svc.stream.listen((_) {}, onError: errors.add);
    svc.start();

    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(errors, isNotEmpty);

    await sub.cancel();
    await svc.stop();
  });
}
