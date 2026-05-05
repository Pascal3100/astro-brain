import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/calibration.dart';
import '../models/system_state.dart';
import 'pi_host.dart';

enum Axis {
  alt,
  az;

  String toJson() => name;
}

enum Direction {
  plus,
  minus;

  String toJson() => this == Direction.plus ? '+' : '-';
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Client REST vers le backend FastAPI. Un timeout court (3 s) sur toutes
/// les requêtes : l'UI doit savoir rapidement que le Pi est injoignable
/// pour afficher l'état offline.
class ApiService {
  ApiService({required this.host, http.Client? client})
      : _client = client ?? http.Client();

  final PiHost host;
  final http.Client _client;

  static const Duration _timeout = Duration(seconds: 3);

  Future<SystemState> fetchState() async {
    final resp = await _client.get(host.restUri('/state')).timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('GET /state failed', statusCode: resp.statusCode);
    }
    return SystemState.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<void> slew({
    required Axis axis,
    required Direction direction,
    required int rate,
  }) async {
    await _post('/slew', {
      'axis': axis.toJson(),
      'direction': direction.toJson(),
      'rate': rate,
    });
  }

  Future<void> stop({Axis? axis}) async {
    await _post('/stop', axis == null ? {} : {'axis': axis.toJson()});
  }

  Future<void> setTracking(bool enabled) async {
    await _post('/tracking', {'enabled': enabled});
  }

  Future<void> _post(String path, Map<String, dynamic> body) async {
    final resp = await _client
        .post(
          host.restUri(path),
          headers: const {'content-type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('POST $path failed', statusCode: resp.statusCode);
    }
  }

  // -------------------------------------------------------------------------
  // Calibration endpoints
  // -------------------------------------------------------------------------

  /// Retourne le statut persisté de calibration pour [sensorId].
  ///
  /// Toujours 200 ; `payload` est `null` si le capteur n'a jamais été calibré.
  Future<CalibrationStatus> getCalibrationStatus(String sensorId) async {
    final resp = await _client
        .get(host.restUri('/calibration/$sensorId'))
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException(
        'GET /calibration/$sensorId failed',
        statusCode: resp.statusCode,
      );
    }
    return CalibrationStatus.fromJson(
      jsonDecode(resp.body) as Map<String, dynamic>,
    );
  }

  /// Démarre une session de calibration pour [sensorId].
  ///
  /// Retourne le `session_id` (hex) fourni par le backend (202 Accepted).
  Future<String> startCalibration(String sensorId) async {
    final resp = await _client
        .post(host.restUri('/calibration/$sensorId/start'))
        .timeout(_timeout);
    if (resp.statusCode != 202) {
      throw ApiException(
        'POST /calibration/$sensorId/start failed',
        statusCode: resp.statusCode,
      );
    }
    final json = jsonDecode(resp.body) as Map<String, dynamic>;
    return json['session_id'] as String;
  }

  /// Finalise la session active pour [sensorId] et retourne le statut
  /// persisté mis à jour.
  Future<CalibrationStatus> finalizeCalibration(String sensorId) async {
    final resp = await _client
        .post(host.restUri('/calibration/$sensorId/finalize'))
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException(
        'POST /calibration/$sensorId/finalize failed',
        statusCode: resp.statusCode,
      );
    }
    return CalibrationStatus.fromJson(
      jsonDecode(resp.body) as Map<String, dynamic>,
    );
  }

  /// Annule la session active pour [sensorId] sans persister les données.
  ///
  /// Idempotent (le backend retourne toujours `{"ok": true}`).
  Future<void> abortCalibration(String sensorId) async {
    final resp = await _client
        .post(host.restUri('/calibration/$sensorId/abort'))
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException(
        'POST /calibration/$sensorId/abort failed',
        statusCode: resp.statusCode,
      );
    }
  }

  void dispose() => _client.close();
}
