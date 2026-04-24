import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/system_state.dart';
import 'pi_host.dart';
import 'sse_event.dart';
import 'sse_parser.dart';

/// Service SSE qui maintient une connexion permanente vers `/events` et
/// expose un [stream] de [SystemState] complets.
///
/// - Au `snapshot` initial : émet directement l'état parsé.
/// - Sur `update` : applique le diff sur l'état courant, émet l'état complet.
/// - Sur déconnexion ou erreur : tente un reconnect avec back-off
///   exponentiel (1s, 2s, 4s, plafond 10s). Le serveur renverra un
///   nouveau `snapshot` à la reconnexion, donc pas de rattrapage
///   applicatif à faire.
class EventStreamService {
  EventStreamService({
    required this.host,
    http.Client Function()? clientFactory,
  }) : _clientFactory = clientFactory ?? http.Client.new;

  final PiHost host;
  final http.Client Function() _clientFactory;

  final StreamController<SystemState> _out =
      StreamController<SystemState>.broadcast();
  SystemState? _current;
  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Timer? _reconnectTimer;
  int _retryIndex = 0;
  bool _stopped = false;

  static const List<Duration> _backoff = [
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
    Duration(seconds: 10),
  ];

  Stream<SystemState> get stream => _out.stream;

  /// Démarre la connexion. Idempotent : un appel pendant qu'une connexion
  /// est déjà active ne fait rien.
  void start() {
    if (_stopped) return;
    _connect();
  }

  Future<void> stop() async {
    _stopped = true;
    _reconnectTimer?.cancel();
    await _sub?.cancel();
    _client?.close();
    await _out.close();
  }

  void _connect() {
    final client = _clientFactory();
    _client = client;
    final req = http.Request('GET', host.sseUri('/events'))
      ..headers['accept'] = 'text/event-stream';
    final parser = SseParser(_onEvent);

    client.send(req).then((resp) {
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
    }).catchError((Object _) {
      _scheduleReconnect();
    });
  }

  void _onEvent(SseEvent event) {
    if (event.event == 'snapshot') {
      final json = jsonDecode(event.data) as Map<String, dynamic>;
      _current = SystemState.fromJson(json);
      _out.add(_current!);
    } else if (event.event == 'update') {
      final current = _current;
      if (current == null) return; // update avant snapshot : on ignore
      final json = jsonDecode(event.data) as Map<String, dynamic>;
      _current = current.applyUpdate(json);
      _out.add(_current!);
    }
  }

  void _scheduleReconnect() {
    if (_stopped) return;
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
