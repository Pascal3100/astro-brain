import 'sse_event.dart';

/// Parser text/event-stream conforme à la spec WHATWG (version minimale,
/// suffisante pour notre backend) : chaque bloc se termine par une ligne
/// vide ; `event:` définit le type, `data:` ajoute une ligne au buffer.
class SseParser {
  SseParser(this.onEvent);

  final void Function(SseEvent event) onEvent;
  final StringBuffer _lineBuf = StringBuffer();

  String? _eventType;
  final StringBuffer _dataBuf = StringBuffer();

  void feed(String chunk) {
    for (var i = 0; i < chunk.length; i++) {
      final c = chunk[i];
      if (c == '\n') {
        _processLine(_lineBuf.toString());
        _lineBuf.clear();
      } else if (c != '\r') {
        _lineBuf.write(c);
      }
    }
  }

  void _processLine(String line) {
    if (line.isEmpty) {
      _dispatch();
      return;
    }
    if (line.startsWith(':')) return; // commentaire / ping

    final colon = line.indexOf(':');
    final field = colon == -1 ? line : line.substring(0, colon);
    var value = colon == -1 ? '' : line.substring(colon + 1);
    if (value.startsWith(' ')) value = value.substring(1);

    switch (field) {
      case 'event':
        _eventType = value;
        break;
      case 'data':
        if (_dataBuf.isNotEmpty) _dataBuf.write('\n');
        _dataBuf.write(value);
        break;
      // `id:` et `retry:` ignorés en v0.1.
    }
  }

  void _dispatch() {
    if (_dataBuf.isEmpty && _eventType == null) return;
    onEvent(SseEvent(
      event: _eventType ?? 'message',
      data: _dataBuf.toString(),
    ));
    _eventType = null;
    _dataBuf.clear();
  }
}
