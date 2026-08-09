import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/about.dart';
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

  /// Déclenche une reconnexion de la monture (non bloquant côté backend :
  /// la progression revient par SSE `/state`).
  Future<void> reconnectMount() async {
    await _post('/mount/reconnect', const {});
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
  // Helpers JSON génériques (utilisés par les repositories)
  // -------------------------------------------------------------------------

  /// GET [path] et retourne le JSON décodé. Les paramètres de requête
  /// passent par [query] (encodage correct via `Uri.http`), pas dans [path].
  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? query,
  }) async {
    final resp = await _client.get(host.restUri(path, query)).timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('GET $path failed', statusCode: resp.statusCode);
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// POST [path] avec [body] JSON et retourne le JSON décodé.
  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body,
  ) async {
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
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// DELETE [path]. Le backend renvoie 204 No Content sur succès.
  Future<void> delete(String path) async {
    final resp = await _client.delete(host.restUri(path)).timeout(_timeout);
    if (resp.statusCode != 204 && resp.statusCode != 200) {
      throw ApiException('DELETE $path failed', statusCode: resp.statusCode);
    }
  }

  // -------------------------------------------------------------------------
  // Calibration endpoints
  // -------------------------------------------------------------------------

  /// Retourne le statut persisté de calibration pour [sensorId].
  ///
  /// Toujours 200 ; `payload` est `null` si le capteur n'a jamais été calibré.
  Future<CalibrationStatus> getCalibrationStatus(String sensorId) async {
    final encoded = Uri.encodeComponent(sensorId);
    final resp = await _client
        .get(host.restUri('/calibration/$encoded'))
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
    final encoded = Uri.encodeComponent(sensorId);
    final resp = await _client
        .post(host.restUri('/calibration/$encoded/start'))
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
    final encoded = Uri.encodeComponent(sensorId);
    final resp = await _client
        .post(host.restUri('/calibration/$encoded/finalize'))
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
    final encoded = Uri.encodeComponent(sensorId);
    final resp = await _client
        .post(host.restUri('/calibration/$encoded/abort'))
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException(
        'POST /calibration/$sensorId/abort failed',
        statusCode: resp.statusCode,
      );
    }
  }

  // -------------------------------------------------------------------------
  // About endpoint
  // -------------------------------------------------------------------------

  /// Retourne les informations système du backend (`GET /about`).
  ///
  /// Toujours 200 — pas de 404 possible.
  Future<AboutInfo> getAbout() async {
    final resp = await _client
        .get(host.restUri('/about'))
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('GET /about failed', statusCode: resp.statusCode);
    }
    return AboutInfo.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  void dispose() => _client.close();
}
