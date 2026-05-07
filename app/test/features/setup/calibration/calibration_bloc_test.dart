import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/features/setup/calibration/calibration_bloc.dart';
import 'package:astro_brain/models/calibration.dart' show Lis3mdlOffsets;
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

CalibrationProgress _progress({
  required int n,
  double sigma = 0.0,
  double cov = 0.0,
}) => CalibrationProgress(
  state: CalibrationState.sampling,
  samplesN: n,
  coveragePct: cov,
  sigma: sigma,
);

ApiService _apiWith(MockClientHandler handler) =>
    ApiService(host: const PiHost(), client: MockClient(handler));

const _adxlStatusJson =
    '{"sensor_id":"adxl345_mount",'
    '"calibrated_at":"2026-05-06T12:00:00Z",'
    '"payload":{"bias":[0.01,0.02,0.99],"sigma":0.03}}';

const _lisStatusJson =
    '{"sensor_id":"lis3mdl",'
    '"calibrated_at":"2026-05-06T12:00:00Z",'
    '"payload":{'
    '"offsets":[0.1,0.2,0.3],'
    '"scale_matrix":[[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],'
    '"coverage_pct":92.0,'
    '"residual":0.005}}';

const _adxlProgressJson =
    '{"state":"sampling","samples_n":150,"coverage_pct":0.0,'
    '"sigma":0.04}';

const _lisProgressJson =
    '{"state":"sampling","samples_n":600,"coverage_pct":85.0,'
    '"sigma":0.0,"hint":"Continuez les rotations"}';

void main() {
  group('CalibrationBloc — gates state machine partagée', () {
    blocTest<CalibrationBloc, CalibrationBlocState>(
      'happy path ADXL : start → progress → finalize → done',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return CalibrationBloc(
          api: _apiWith((req) async {
            if (req.url.path == '/calibration/adxl345_mount/start') {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path == '/calibration/adxl345_mount/finalize') {
              return http.Response(_adxlStatusJson, 200);
            }
            return http.Response('not found', 404);
          }),
          sensorId: 'adxl345_mount',
          finalizeGate: adxlCanFinalize,
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const CalibrationStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(CalibrationProgressReceived(_progress(n: 50, sigma: 0.10)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isFalse);
        bloc.add(CalibrationProgressReceived(_progress(n: 150, sigma: 0.04)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isTrue);
        bloc.add(const CalibrationFinalizeRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, CalibrationState.done);
        expect(bloc.state.finalizedStatus, isNotNull);
        expect(bloc.state.finalizedStatus!.sensorId, 'adxl345_mount');
      },
    );

    blocTest<CalibrationBloc, CalibrationBlocState>(
      'happy path LIS3MDL : couverture gate la finalisation',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return CalibrationBloc(
          api: _apiWith((req) async {
            if (req.url.path == '/calibration/lis3mdl/start') {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path == '/calibration/lis3mdl/finalize') {
              return http.Response(_lisStatusJson, 200);
            }
            return http.Response('not found', 404);
          }),
          sensorId: 'lis3mdl',
          finalizeGate: lis3mdlCanFinalize,
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const CalibrationStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(CalibrationProgressReceived(_progress(n: 550, cov: 50.0)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isFalse);
        bloc.add(CalibrationProgressReceived(_progress(n: 600, cov: 85.0)));
        await Future<void>.delayed(Duration.zero);
        expect(bloc.state.canFinalize, isTrue);
        bloc.add(const CalibrationFinalizeRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, CalibrationState.done);
        expect(bloc.state.finalizedStatus, isNotNull);
        expect(bloc.state.finalizedStatus!.sensorId, 'lis3mdl');
        expect(bloc.state.finalizedStatus!.payload, isA<Lis3mdlOffsets>());
      },
    );

    blocTest<CalibrationBloc, CalibrationBlocState>(
      'abort : start → abort → state.aborted',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        return CalibrationBloc(
          api: _apiWith((req) async {
            if (req.url.path.endsWith('/start')) {
              return http.Response('{"session_id":"abc"}', 202);
            }
            if (req.url.path.endsWith('/abort')) {
              return http.Response('{"ok":true}', 200);
            }
            return http.Response('nope', 404);
          }),
          sensorId: 'adxl345_mount',
          finalizeGate: adxlCanFinalize,
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const CalibrationStarted());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        bloc.add(const CalibrationAbortRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.status, CalibrationState.aborted);
      },
    );

    blocTest<CalibrationBloc, CalibrationBlocState>(
      'erreur 409 sur start → state.error',
      build: () => CalibrationBloc(
        api: _apiWith((req) async => http.Response('conflict', 409)),
        sensorId: 'adxl345_mount',
        finalizeGate: adxlCanFinalize,
        progressStream: (_) => const Stream<CalibrationProgress>.empty(),
      ),
      act: (bloc) async {
        bloc.add(const CalibrationStarted());
        await Future<void>.delayed(const Duration(milliseconds: 20));
      },
      verify: (bloc) {
        expect(bloc.state.status, CalibrationState.error);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.errorMessage, contains('409'));
      },
    );

    blocTest<CalibrationBloc, CalibrationBlocState>(
      'SSE end pendant sampling → state.error',
      build: () {
        final ctrl = StreamController<CalibrationProgress>.broadcast();
        scheduleMicrotask(() => ctrl.close());
        return CalibrationBloc(
          api: _apiWith((req) async {
            if (req.url.path.endsWith('/start')) {
              return http.Response('{"session_id":"abc"}', 202);
            }
            return http.Response('nope', 404);
          }),
          sensorId: 'adxl345_tube',
          finalizeGate: adxlCanFinalize,
          progressStream: (_) => ctrl.stream,
        );
      },
      act: (bloc) async {
        bloc.add(const CalibrationStarted());
        await Future<void>.delayed(const Duration(milliseconds: 50));
      },
      verify: (bloc) {
        expect(bloc.state.status, CalibrationState.error);
        expect(bloc.state.errorMessage, contains('Stream'));
      },
    );

    test('canFinalize ADXL : sigma et samples gatent indépendamment', () {
      final state = CalibrationBlocState(
        status: CalibrationState.sampling,
        finalizeGate: adxlCanFinalize,
      );
      expect(state.canFinalize, isFalse);

      // sigma >= seuil → false
      final s1 = state.copyWith(
        progress: _progress(n: 200, sigma: kAdxlSigmaThreshold),
      );
      expect(s1.canFinalize, isFalse);

      // samples < min → false
      final s2 = state.copyWith(
        progress: _progress(n: kAdxlMinSamples - 1, sigma: 0.01),
      );
      expect(s2.canFinalize, isFalse);

      // ok
      final s3 = state.copyWith(
        progress: _progress(n: kAdxlMinSamples, sigma: 0.01),
      );
      expect(s3.canFinalize, isTrue);
    });

    test('canFinalize LIS3MDL : samples et coverage gatent indépendamment', () {
      final state = CalibrationBlocState(
        status: CalibrationState.sampling,
        finalizeGate: lis3mdlCanFinalize,
      );
      expect(state.canFinalize, isFalse);

      // samples=499, coverage=80 → false (samples sous le seuil).
      final s1 = state.copyWith(
        progress: _progress(
          n: kLis3mdlMinSamples - 1,
          cov: kLis3mdlCoverageThreshold,
        ),
      );
      expect(s1.canFinalize, isFalse);

      // samples=500, coverage=79.9 → false (couverture sous le seuil).
      final s2 = state.copyWith(
        progress: _progress(n: kLis3mdlMinSamples, cov: 79.9),
      );
      expect(s2.canFinalize, isFalse);

      // samples=500, coverage=80.0 → true (limites incluses).
      final s3 = state.copyWith(
        progress: _progress(
          n: kLis3mdlMinSamples,
          cov: kLis3mdlCoverageThreshold,
        ),
      );
      expect(s3.canFinalize, isTrue);
    });

    test('canFinalize false hors phase sampling', () {
      final s = CalibrationBlocState(
        status: CalibrationState.computing,
        finalizeGate: adxlCanFinalize,
      ).copyWith(progress: _progress(n: 999, sigma: 0.001));
      expect(s.canFinalize, isFalse);
    });

    // Sanity-check : les payloads SSE JSON décodent sans crash.
    test('CalibrationProgress.fromJson parse les payloads ADXL et LIS3MDL', () {
      final adxl = CalibrationProgress.fromJson(
        jsonDecode(_adxlProgressJson) as Map<String, dynamic>,
      );
      expect(adxl.samplesN, 150);
      expect(adxl.sigma, closeTo(0.04, 1e-9));

      final lis = CalibrationProgress.fromJson(
        jsonDecode(_lisProgressJson) as Map<String, dynamic>,
      );
      expect(lis.samplesN, 600);
      expect(lis.coveragePct, closeTo(85.0, 1e-9));
      expect(lis.hint, 'Continuez les rotations');
    });
  });
}
