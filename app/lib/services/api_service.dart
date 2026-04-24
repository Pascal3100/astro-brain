import 'dart:convert';

import 'package:http/http.dart' as http;

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

  void dispose() => _client.close();
}
