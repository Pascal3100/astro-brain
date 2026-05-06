import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/features/setup/calibration/adxl_tube_bloc.dart';
import 'package:astro_brain/features/setup/calibration/adxl_tube_event.dart';
import 'package:astro_brain/features/setup/calibration/adxl_tube_state.dart';
import 'package:astro_brain/models/calibration.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

CalibrationProgress _progress({required int n, required double sigma}) =>
    CalibrationProgress(
      state: CalibrationState.sampling,
      samplesN: n,
      coveragePct: 0.0,
      sigma: sigma,
    );

ApiService _apiWith(MockClientHandler handler) =>
    ApiService(host: const PiHost(), client: MockClient(handler));

const _statusJson =
    '{"sensor_id":"adxl345_tube",'
    '"calibrated_at":"2026-05-06T12:00:00Z",'
    '"payload":{"bias":[0.01,0.02,0.99],"sigma":0.03,"zero_alt_deg":0.0}}';

const _progressJson =
    '{"state":"sampling","samples_n":150,"coverage_pct":0.0,'
    '"sigma":0.04}';

void main() {
  group('AdxlTubeBloc', () {
    blocTest<AdxlTubeBloc, AdxlTubeState>(
      'happy path : start → progress → finalize → done',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return AdxlTubeBloc(
          api: _apiWith((req) async {
            if (req.url.path == '/calibration/adxl345_tube/start') {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path == '/calibration/adxl345_tube/finalize') {
              return http.Response(_statusJson, 200);
            }
            return http.Response('not found', 404);
          }),
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const AdxlTubeStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(AdxlTubeProgressReceived(_progress(n: 50, sigma: 0.10)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isFalse);
        bloc.add(AdxlTubeProgressReceived(_progress(n: 150, sigma: 0.04)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isTrue);
        bloc.add(const AdxlTubeFinalizeRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlTubeStatus.done);
        expect(bloc.state.finalizedStatus, isNotNull);
        expect(bloc.state.finalizedStatus!.sensorId, 'adxl345_tube');
      },
    );

    blocTest<AdxlTubeBloc, AdxlTubeState>(
      'abort : start → abort → state.aborted',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return AdxlTubeBloc(
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
        bloc.add(const AdxlTubeStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(const AdxlTubeAbortRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlTubeStatus.aborted);
      },
    );

    blocTest<AdxlTubeBloc, AdxlTubeState>(
      'erreur 409 sur start → state.error',
      build: () {
        return AdxlTubeBloc(
          api: _apiWith((req) async => http.Response('conflict', 409)),
          progressStream: (_) => const Stream<CalibrationProgress>.empty(),
        );
      },
      act: (bloc) async {
        bloc.add(const AdxlTubeStarted());
        await Future<void>.delayed(const Duration(milliseconds: 20));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlTubeStatus.error);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.errorMessage, contains('409'));
      },
    );

    blocTest<AdxlTubeBloc, AdxlTubeState>(
      'SSE end pendant sampling → state.error',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        scheduleMicrotask(() => ctrl.close());
        return AdxlTubeBloc(
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
        bloc.add(const AdxlTubeStarted());
        await Future<void>.delayed(const Duration(milliseconds: 50));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlTubeStatus.error);
        expect(bloc.state.errorMessage, contains('Stream'));
      },
    );

    test('canFinalize false sur sigma trop grand', () {
      const state = AdxlTubeState(status: AdxlTubeStatus.sampling);
      expect(state.canFinalize, isFalse);

      final s1 = state.copyWith(
        progress: _progress(n: 200, sigma: adxlTubeSigmaThreshold),
      );
      expect(s1.canFinalize, isFalse);

      final s2 = state.copyWith(
        progress: _progress(n: adxlTubeMinSamples - 1, sigma: 0.01),
      );
      expect(s2.canFinalize, isFalse);

      final s3 = state.copyWith(
        progress: _progress(n: adxlTubeMinSamples, sigma: 0.01),
      );
      expect(s3.canFinalize, isTrue);
    });

    test('CalibrationProgress.fromJson parse le payload SSE', () {
      final p = CalibrationProgress.fromJson(
        jsonDecode(_progressJson) as Map<String, dynamic>,
      );
      expect(p.samplesN, 150);
      expect(p.sigma, closeTo(0.04, 1e-9));
    });
  });
}
