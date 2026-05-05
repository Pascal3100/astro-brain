import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/sensor_readings.dart';
import 'pi_host.dart';
import 'sse_event.dart';
import 'sse_parser.dart';

/// Service SSE qui maintient une connexion permanente vers
/// `/sensors/tilt/stream?hz=N` et expose un [stream] de [TiltReading].
///
/// - Chaque event `tilt` est un payload JSON auto-suffisant.
/// - Sur déconnexion ou erreur : tente un reconnect avec back-off
///   exponentiel (1s, 2s, 4s, plafond 10s). Le compteur est remis à 0
///   à chaque connexion réussie (HTTP 200).
class TiltStreamService {
  TiltStreamService({
    required this.host,
    this.hz = 5,
    http.Client Function()? clientFactory,
  }) : _clientFactory = clientFactory ?? http.Client.new;

  final PiHost host;

  /// Fréquence d'échantillonnage souhaitée (1..10 côté backend, clampé).
  final int hz;

  final http.Client Function() _clientFactory;

  final StreamController<TiltReading> _out =
      StreamController<TiltReading>.broadcast();
  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Timer? _reconnectTimer;
  int _retryIndex = 0;

  static const List<Duration> _backoff = [
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
    Duration(seconds: 10),
  ];

  Stream<TiltReading> get stream => _out.stream;

  /// Démarre la connexion. Idempotent : un appel pendant qu'une connexion
  /// est déjà active ne fait rien. Sans effet si [dispose] a déjà été appelé.
  void start() {
    if (_out.isClosed) return;
    _connect();
  }

  /// Coupe la connexion courante sans fermer le stream [_out].
  Future<void> stop() async {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    await _sub?.cancel();
    _client?.close();
    _sub = null;
    _client = null;
  }

  /// Fermeture définitive du service (fin de vie).
  Future<void> dispose() async {
    await stop();
    await _out.close();
  }

  void _connect() {
    final client = _clientFactory();
    _client = client;
    final uri = host
        .sseUri('/sensors/tilt/stream')
        .replace(queryParameters: {'hz': '$hz'});
    final req = http.Request('GET', uri)
      ..headers['accept'] = 'text/event-stream';
    final parser = SseParser(_onEvent);

    client
        .send(req)
        .then((resp) {
          if (resp.statusCode != 200) {
            _scheduleReconnect();
            return;
          }
          _retryIndex = 0;
          _sub = resp.stream.listen(
            (chunk) => parser.feed(utf8.decode(chunk, allowMalformed: true)),
            onError: (_) => _scheduleReconnect(),
            onDone: _scheduleReconnect,
            cancelOnError: true,
          );
        })
        .catchError((Object _) {
          _scheduleReconnect();
        });
  }

  void _onEvent(SseEvent event) {
    if (event.event != 'tilt') return;
    final json = jsonDecode(event.data) as Map<String, dynamic>;
    _out.add(TiltReading.fromJson(json));
  }

  void _scheduleReconnect() {
    if (_out.isClosed) return;
    _sub?.cancel();
    _client?.close();
    _sub = null;
    _client = null;

    final delay = _backoff[_retryIndex.clamp(0, _backoff.length - 1)];
    _retryIndex++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, _connect);
  }
}
