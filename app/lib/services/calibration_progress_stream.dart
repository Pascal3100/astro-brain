import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/calibration.dart';
import 'pi_host.dart';
import 'sse_event.dart';
import 'sse_parser.dart';

/// Helper SSE one-shot pour les sessions de calibration.
///
/// Diffère de [CompassStreamService] : pas de reconnect,
/// le stream se termine naturellement quand le backend envoie l'event `end`
/// (après finalize/abort) ou quand la connexion ferme. Le bloc consommateur
/// observe la fin via `onDone`.
///
/// Filtrage :
/// - `event: progress` → décodé en [CalibrationProgress] et émis
/// - `event: end` → ferme le stream proprement
/// - autres events → ignorés silencieusement
class CalibrationProgressStream {
  CalibrationProgressStream({
    required this.host,
    required this.sensorId,
    required this.sessionId,
    http.Client Function()? clientFactory,
  }) : _clientFactory = clientFactory ?? http.Client.new;

  final PiHost host;
  final String sensorId;
  final String sessionId;
  final http.Client Function() _clientFactory;

  final StreamController<CalibrationProgress> _out =
      StreamController<CalibrationProgress>();
  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  bool _opened = false;

  /// Démarre la connexion SSE et retourne le stream à consommer.
  ///
  /// Doit être appelé une seule fois par instance. Le stream émet zéro ou
  /// plusieurs [CalibrationProgress] puis se ferme.
  Stream<CalibrationProgress> open() {
    if (_opened) {
      throw StateError('CalibrationProgressStream.open() already called');
    }
    _opened = true;
    _connect();
    return _out.stream;
  }

  /// Ferme prématurément le stream (ex. bloc fermé avant fin de session).
  Future<void> cancel() async {
    await _sub?.cancel();
    _client?.close();
    _sub = null;
    _client = null;
    if (!_out.isClosed) await _out.close();
  }

  void _connect() {
    final client = _clientFactory();
    _client = client;
    final uri = host
        .sseUri('/calibration/$sensorId/stream')
        .replace(queryParameters: {'session_id': sessionId});
    final req = http.Request('GET', uri)
      ..headers['accept'] = 'text/event-stream';
    final parser = SseParser(_onEvent);

    client
        .send(req)
        .then((resp) {
          if (resp.statusCode != 200) {
            _close();
            return;
          }
          _sub = resp.stream.listen(
            (chunk) => parser.feed(utf8.decode(chunk, allowMalformed: true)),
            onError: (_) => _close(),
            onDone: _close,
            cancelOnError: true,
          );
        })
        .catchError((Object _) {
          _close();
        });
  }

  void _onEvent(SseEvent event) {
    if (event.event == 'end') {
      _close();
      return;
    }
    if (event.event != 'progress') return;
    try {
      final json = jsonDecode(event.data) as Map<String, dynamic>;
      _out.add(CalibrationProgress.fromJson(json));
    } catch (_) {
      // Payload mal formé : drop sans tuer la souscription. Voir le commentaire
      // équivalent dans CompassStreamService.
    }
  }

  void _close() {
    _sub?.cancel();
    _client?.close();
    _sub = null;
    _client = null;
    if (!_out.isClosed) _out.close();
  }
}
