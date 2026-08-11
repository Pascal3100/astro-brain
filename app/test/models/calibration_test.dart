import 'package:astro_brain/models/calibration.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // -------------------------------------------------------------------------
  // CalibrationState
  // -------------------------------------------------------------------------

  group('CalibrationState.fromJson', () {
    test('valeurs connues mappées correctement', () {
      expect(CalibrationState.fromJson('idle'), CalibrationState.idle);
      expect(CalibrationState.fromJson('sampling'), CalibrationState.sampling);
      expect(CalibrationState.fromJson('computing'), CalibrationState.computing);
      expect(CalibrationState.fromJson('done'), CalibrationState.done);
      expect(CalibrationState.fromJson('aborted'), CalibrationState.aborted);
      expect(CalibrationState.fromJson('error'), CalibrationState.error);
    });

    test('valeur inconnue retourne idle (défensif)', () {
      expect(CalibrationState.fromJson('garbage'), CalibrationState.idle);
      expect(CalibrationState.fromJson(''), CalibrationState.idle);
    });
  });

  // -------------------------------------------------------------------------
  // Lis3mdlOffsets
  // -------------------------------------------------------------------------

  group('Lis3mdlOffsets.fromJson', () {
    const lisJson = <String, dynamic>{
      'offsets': [10.0, -5.0, 3.0],
      'scale_matrix': [
        [1.02, 0.0, 0.0],
        [0.0, 0.98, 0.0],
        [0.0, 0.0, 1.05],
      ],
      'coverage_pct': 87.5,
      'residual': 0.012,
    };

    test('parse tous les champs', () {
      final offsets = Lis3mdlOffsets.fromJson(lisJson);
      expect(offsets.offsets, (10.0, -5.0, 3.0));
      expect(offsets.scaleMatrix.length, 3);
      expect(offsets.scaleMatrix[0], [1.02, 0.0, 0.0]);
      expect(offsets.scaleMatrix[1], [0.0, 0.98, 0.0]);
      expect(offsets.scaleMatrix[2], [0.0, 0.0, 1.05]);
      expect(offsets.coveragePct, 87.5);
      expect(offsets.residual, 0.012);
    });

    test('égalité Equatable', () {
      final a = Lis3mdlOffsets.fromJson(lisJson);
      final b = Lis3mdlOffsets.fromJson(lisJson);
      expect(a, equals(b));
    });
  });

  // -------------------------------------------------------------------------
  // CalibrationProgress
  // -------------------------------------------------------------------------

  group('CalibrationProgress.fromJson', () {
    test('parse avec hint et residual renseignés', () {
      final json = <String, dynamic>{
        'state': 'sampling',
        'samples_n': 42,
        'coverage_pct': 35.0,
        'sigma': 0.012,
        'hint': 'Maintenir immobile',
        'residual': null,
      };
      final progress = CalibrationProgress.fromJson(json);
      expect(progress.state, CalibrationState.sampling);
      expect(progress.samplesN, 42);
      expect(progress.coveragePct, 35.0);
      expect(progress.sigma, 0.012);
      expect(progress.hint, 'Maintenir immobile');
      expect(progress.residual, isNull);
    });

    test('hint null et residual null acceptés', () {
      final json = <String, dynamic>{
        'state': 'idle',
        'samples_n': 0,
        'coverage_pct': 0.0,
        'sigma': 0.0,
        'hint': null,
        'residual': null,
      };
      final progress = CalibrationProgress.fromJson(json);
      expect(progress.hint, isNull);
      expect(progress.residual, isNull);
    });

    test('residual présent en phase done', () {
      final json = <String, dynamic>{
        'state': 'done',
        'samples_n': 120,
        'coverage_pct': 92.0,
        'sigma': 0.004,
        'hint': null,
        'residual': 0.007,
      };
      final progress = CalibrationProgress.fromJson(json);
      expect(progress.state, CalibrationState.done);
      expect(progress.residual, 0.007);
    });

    test('égalité Equatable', () {
      final json = <String, dynamic>{
        'state': 'sampling',
        'samples_n': 10,
        'coverage_pct': 5.0,
        'sigma': 0.01,
        'hint': null,
        'residual': null,
      };
      expect(
        CalibrationProgress.fromJson(json),
        equals(CalibrationProgress.fromJson(json)),
      );
    });
  });

  // -------------------------------------------------------------------------
  // CalibrationStatus
  // -------------------------------------------------------------------------

  group('CalibrationStatus.fromJson', () {
    test('payload null + calibrated_at null (jamais calibré)', () {
      final json = <String, dynamic>{
        'sensor_id': 'adxl345_mount',
        'calibrated_at': null,
        'payload': null,
      };
      final status = CalibrationStatus.fromJson(json);
      expect(status.sensorId, 'adxl345_mount');
      expect(status.calibratedAt, isNull);
      expect(status.payload, isNull);
    });

    test('sensor_id lis3mdl → payload est Lis3mdlOffsets', () {
      final json = <String, dynamic>{
        'sensor_id': 'lis3mdl',
        'calibrated_at': '2026-05-05T22:00:00+00:00',
        'payload': {
          'offsets': [10.0, -5.0, 3.0],
          'scale_matrix': [
            [1.02, 0.0, 0.0],
            [0.0, 0.98, 0.0],
            [0.0, 0.0, 1.05],
          ],
          'coverage_pct': 87.5,
          'residual': 0.012,
        },
      };
      final status = CalibrationStatus.fromJson(json);
      expect(status.payload, isA<Lis3mdlOffsets>());
      final lis = status.payload as Lis3mdlOffsets;
      expect(lis.coveragePct, 87.5);
      expect(status.calibratedAt, isNotNull);
      expect(
        status.calibratedAt,
        DateTime.parse('2026-05-05T22:00:00+00:00'),
      );
    });

    test('égalité Equatable', () {
      final json = <String, dynamic>{
        'sensor_id': 'adxl345_mount',
        'calibrated_at': null,
        'payload': null,
      };
      expect(
        CalibrationStatus.fromJson(json),
        equals(CalibrationStatus.fromJson(json)),
      );
    });
  });
}
