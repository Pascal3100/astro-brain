import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/features/setup/calibration/adxl_mount_bloc.dart';
import 'package:astro_brain/features/setup/calibration/adxl_mount_event.dart';
import 'package:astro_brain/features/setup/calibration/adxl_mount_state.dart';
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
    '{"sensor_id":"adxl345_mount",'
    '"calibrated_at":"2026-05-06T12:00:00Z",'
    '"payload":{"bias":[0.01,0.02,0.99],"sigma":0.03}}';

const _progressJson =
    '{"state":"sampling","samples_n":150,"coverage_pct":0.0,'
    '"sigma":0.04}';

void main() {
  group('AdxlMountBloc', () {
    blocTest<AdxlMountBloc, AdxlMountState>(
      'happy path : start → progress → finalize → done',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return AdxlMountBloc(
          api: _apiWith((req) async {
            if (req.url.path == '/calibration/adxl345_mount/start') {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path == '/calibration/adxl345_mount/finalize') {
              return http.Response(_statusJson, 200);
            }
            return http.Response('not found', 404);
          }),
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const AdxlMountStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        // Push progress events (non-finalisable puis finalisable).
        bloc.add(AdxlMountProgressReceived(_progress(n: 50, sigma: 0.10)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isFalse);
        bloc.add(AdxlMountProgressReceived(_progress(n: 150, sigma: 0.04)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isTrue);
        bloc.add(const AdxlMountFinalizeRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlMountStatus.done);
        expect(bloc.state.finalizedStatus, isNotNull);
        expect(bloc.state.finalizedStatus!.sensorId, 'adxl345_mount');
      },
    );

    blocTest<AdxlMountBloc, AdxlMountState>(
      'abort : start → abort → state.aborted',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return AdxlMountBloc(
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
        bloc.add(const AdxlMountStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(const AdxlMountAbortRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlMountStatus.aborted);
      },
    );

    blocTest<AdxlMountBloc, AdxlMountState>(
      'erreur 409 sur start → state.error',
      build: () {
        return AdxlMountBloc(
          api: _apiWith((req) async => http.Response('conflict', 409)),
          progressStream: (_) => const Stream<CalibrationProgress>.empty(),
        );
      },
      act: (bloc) async {
        bloc.add(const AdxlMountStarted());
        await Future<void>.delayed(const Duration(milliseconds: 20));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlMountStatus.error);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.errorMessage, contains('409'));
      },
    );

    blocTest<AdxlMountBloc, AdxlMountState>(
      'SSE end pendant sampling → state.error',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        // Le stream se ferme tout de suite après start.
        scheduleMicrotask(() => ctrl.close());
        return AdxlMountBloc(
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
        bloc.add(const AdxlMountStarted());
        await Future<void>.delayed(const Duration(milliseconds: 50));
      },
      verify: (bloc) {
        expect(bloc.state.status, AdxlMountStatus.error);
        expect(bloc.state.errorMessage, contains('Stream'));
      },
    );

    test('canFinalize false sur sigma trop grand', () {
      const state = AdxlMountState(status: AdxlMountStatus.sampling);
      expect(state.canFinalize, isFalse);

      // sigma >= seuil → false
      final s1 = state.copyWith(
        progress: _progress(n: 200, sigma: adxlSigmaThreshold),
      );
      expect(s1.canFinalize, isFalse);

      // samples < min → false
      final s2 = state.copyWith(
        progress: _progress(n: adxlMinSamples - 1, sigma: 0.01),
      );
      expect(s2.canFinalize, isFalse);

      // ok
      final s3 = state.copyWith(
        progress: _progress(n: adxlMinSamples, sigma: 0.01),
      );
      expect(s3.canFinalize, isTrue);
    });

    // Sanity-check : le payload SSE JSON décode sans crash.
    test('CalibrationProgress.fromJson parse le payload SSE', () {
      final p = CalibrationProgress.fromJson(
        jsonDecode(_progressJson) as Map<String, dynamic>,
      );
      expect(p.samplesN, 150);
      expect(p.sigma, closeTo(0.04, 1e-9));
    });
  });
}
