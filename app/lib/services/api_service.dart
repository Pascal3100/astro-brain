import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/about.dart';
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

/// Extrait `detail` d'un corps d'erreur FastAPI (`{"detail": "..."}`).
/// Best-effort : retourne `null` si le corps n'est pas ce JSON.
String? _detailOf(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      final d = decoded['detail'];
      if (d is String) return d;
    }
  } catch (_) {
    // corps non-JSON : pas de detail
  }
  return null;
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.detail});

  final String message;
  final int? statusCode;

  /// Valeur du champ `detail` du corps JSON d'erreur FastAPI
  /// (`{"detail": "..."}`), ou `null` si le corps n'est pas ce JSON.
  final String? detail;

  @override
  String toString() => 'ApiException($statusCode): $message${detail != null ? ' [$detail]' : ''}';
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
      throw ApiException('POST $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
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
      throw ApiException('GET $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// GET [path] et retourne le JSON décodé, ou `null` si le corps est le
  /// littéral `null`.
  ///
  /// Certaines routes traitent l'absence comme un état nominal (`GET /site`
  /// tant qu'aucun site n'est réglé) : elles répondent 200 + `null` plutôt
  /// que 404, ce que [getJson] ne saurait pas décoder.
  Future<Map<String, dynamic>?> getJsonOrNull(
    String path, {
    Map<String, String>? query,
  }) async {
    final resp = await _client.get(host.restUri(path, query)).timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('GET $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
    }
    return jsonDecode(resp.body) as Map<String, dynamic>?;
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
      throw ApiException('POST $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
    }
    return jsonDecode(resp.body) as Map<String, dynamic>;
  }

  /// PUT [path] avec [body] JSON. Le backend renvoie 204 No Content sur
  /// succès (écriture idempotente : pas de corps de réponse à décoder).
  Future<void> putJson(String path, Map<String, dynamic> body) async {
    final resp = await _client
        .put(
          host.restUri(path),
          headers: const {'content-type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(_timeout);
    if (resp.statusCode != 204 && resp.statusCode != 200) {
      throw ApiException('PUT $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
    }
  }

  /// DELETE [path]. Le backend renvoie 204 No Content sur succès.
  Future<void> delete(String path) async {
    final resp = await _client.delete(host.restUri(path)).timeout(_timeout);
    if (resp.statusCode != 204 && resp.statusCode != 200) {
      throw ApiException('DELETE $path failed', statusCode: resp.statusCode);
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
