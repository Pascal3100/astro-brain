import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/features/setup/calibration/lis3mdl_bloc.dart';
import 'package:astro_brain/features/setup/calibration/lis3mdl_event.dart';
import 'package:astro_brain/features/setup/calibration/lis3mdl_state.dart';
import 'package:astro_brain/models/calibration.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

CalibrationProgress _progress({required int n, required double cov}) =>
    CalibrationProgress(
      state: CalibrationState.sampling,
      samplesN: n,
      coveragePct: cov,
      sigma: 0.0,
    );

ApiService _apiWith(MockClientHandler handler) =>
    ApiService(host: const PiHost(), client: MockClient(handler));

const _statusJson =
    '{"sensor_id":"lis3mdl",'
    '"calibrated_at":"2026-05-06T12:00:00Z",'
    '"payload":{'
    '"offsets":[0.1,0.2,0.3],'
    '"scale_matrix":[[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],'
    '"coverage_pct":92.0,'
    '"residual":0.005}}';

const _progressJson =
    '{"state":"sampling","samples_n":600,"coverage_pct":85.0,'
    '"sigma":0.0,"hint":"Continuez les rotations"}';

void main() {
  group('Lis3mdlBloc', () {
    blocTest<Lis3mdlBloc, Lis3mdlState>(
      'happy path : start → progress → finalize → done',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return Lis3mdlBloc(
          api: _apiWith((req) async {
            if (req.url.path == '/calibration/lis3mdl/start') {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path == '/calibration/lis3mdl/finalize') {
              return http.Response(_statusJson, 200);
            }
            return http.Response('not found', 404);
          }),
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const Lis3mdlStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        // Progress non finalisable (couverture trop basse).
        bloc.add(Lis3mdlProgressReceived(_progress(n: 550, cov: 50.0)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isFalse);
        // Progress finalisable.
        bloc.add(Lis3mdlProgressReceived(_progress(n: 600, cov: 85.0)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isTrue);
        bloc.add(const Lis3mdlFinalizeRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, Lis3mdlStatus.done);
        expect(bloc.state.finalizedStatus, isNotNull);
        expect(bloc.state.finalizedStatus!.sensorId, 'lis3mdl');
        expect(bloc.state.finalizedStatus!.payload, isA<Lis3mdlOffsets>());
      },
    );

    blocTest<Lis3mdlBloc, Lis3mdlState>(
      'abort : start → abort → state.aborted',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return Lis3mdlBloc(
          api: _apiWith((req) async {
            if (req.url.path.endsWith('/start')) {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path.endsWith('/abort')) {
              return http.Response('{"ok":true}', 200);
            }
            return http.Response('nope', 404);
          }),
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const Lis3mdlStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(const Lis3mdlAbortRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, Lis3mdlStatus.aborted);
      },
    );

    blocTest<Lis3mdlBloc, Lis3mdlState>(
      'erreur 409 sur start → state.error',
      build: () {
        return Lis3mdlBloc(
          api: _apiWith((req) async => http.Response('conflict', 409)),
          progressStream: (_) => const Stream<CalibrationProgress>.empty(),
        );
      },
      act: (bloc) async {
        bloc.add(const Lis3mdlStarted());
        await Future<void>.delayed(const Duration(milliseconds: 20));
      },
      verify: (bloc) {
        expect(bloc.state.status, Lis3mdlStatus.error);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.errorMessage, contains('409'));
      },
    );

    blocTest<Lis3mdlBloc, Lis3mdlState>(
      'SSE end pendant sampling → state.error',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        // Le stream se ferme tout de suite après start.
        scheduleMicrotask(() => ctrl.close());
        return Lis3mdlBloc(
          api: _apiWith((req) async {
            if (req.url.path.endsWith('/start')) {
              return http.Response('{"session_id":"abc"}', 202);
            }
            return http.Response('nope', 404);
          }),
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const Lis3mdlStarted());
        await Future<void>.delayed(const Duration(milliseconds: 50));
      },
      verify: (bloc) {
        expect(bloc.state.status, Lis3mdlStatus.error);
        expect(bloc.state.errorMessage, contains('Stream'));
      },
    );

    test('canFinalize : gates samples_n + coverage_pct', () {
      const state = Lis3mdlState(status: Lis3mdlStatus.sampling);
      expect(state.canFinalize, isFalse);

      // samples=499, coverage=80 → false (samples sous le seuil).
      final s1 = state.copyWith(
        progress: _progress(
          n: lis3mdlMinSamples - 1,
          cov: lis3mdlCoverageThreshold,
        ),
      );
      expect(s1.canFinalize, isFalse);

      // samples=500, coverage=79.9 → false (couverture sous le seuil).
      final s2 = state.copyWith(
        progress: _progress(n: lis3mdlMinSamples, cov: 79.9),
      );
      expect(s2.canFinalize, isFalse);

      // samples=500, coverage=80.0 → true (limites incluses).
      final s3 = state.copyWith(
        progress: _progress(
          n: lis3mdlMinSamples,
          cov: lis3mdlCoverageThreshold,
        ),
      );
      expect(s3.canFinalize, isTrue);
    });

    // Sanity-check : le payload SSE JSON décode sans crash.
    test('CalibrationProgress.fromJson parse le payload SSE', () {
      final p = CalibrationProgress.fromJson(
        jsonDecode(_progressJson) as Map<String, dynamic>,
      );
      expect(p.samplesN, 600);
      expect(p.coveragePct, closeTo(85.0, 1e-9));
      expect(p.hint, 'Continuez les rotations');
    });
  });
}
