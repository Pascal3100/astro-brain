import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockStream extends Mock implements EventStreamService {}

SystemState _sample() => SystemState.fromJson(jsonDecode(_snapshotJson));

const _snapshotJson = '''
{"overall":"green","subsystems":{"mount":{"state":"ready","details":{},"since":"2026-04-17T20:31:12Z","message":null},"tracking":{"state":"off","details":{},"since":"2026-04-17T20:30:00Z","message":null},"network":{"state":"client","details":{},"since":"2026-04-17T20:29:00Z","message":null},"system":{"state":"ok","details":{},"since":"2026-04-17T20:29:00Z","message":null}},"seq":1,"ts":"2026-04-17T20:31:12Z"}
''';

void main() {
  late StreamController<SystemState> controller;
  late _MockStream svc;

  setUp(() {
    controller = StreamController<SystemState>.broadcast();
    svc = _MockStream();
    when(() => svc.stream).thenAnswer((_) => controller.stream);
    when(() => svc.start()).thenAnswer((_) {});
    when(() => svc.stop()).thenAnswer((_) async {});
    when(() => svc.dispose()).thenAnswer((_) async {});
  });

  tearDown(() => controller.close());

  blocTest<AppBloc, AppState>(
    'AppStarted connecte le service et passe à connected au premier SystemState',
    build: () => AppBloc(eventStream: svc),
    act: (bloc) async {
      bloc.add(const AppStarted());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      controller.add(_sample());
    },
    wait: const Duration(milliseconds: 50),
    verify: (bloc) {
      expect(bloc.state.connection, ConnectionStatus.connected);
      expect(bloc.state.system?.seq, 1);
      verify(() => svc.start()).called(1);
    },
  );

  blocTest<AppBloc, AppState>(
    'AppConnectionLost repasse en offline',
    build: () => AppBloc(eventStream: svc),
    act: (bloc) async {
      bloc.add(const AppStarted());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      controller.add(_sample());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      bloc.add(const AppConnectionLost());
    },
    wait: const Duration(milliseconds: 50),
    verify: (bloc) {
      expect(bloc.state.connection, ConnectionStatus.offline);
    },
  );
}
