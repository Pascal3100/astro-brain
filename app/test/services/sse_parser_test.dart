import 'package:astro_brain/services/sse_event.dart';
import 'package:astro_brain/services/sse_parser.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SseParser', () {
    test('parse un event simple terminé par ligne vide', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: snapshot\n');
      parser.feed('data: {"ok":true}\n');
      parser.feed('\n');
      expect(events, [SseEvent(event: 'snapshot', data: '{"ok":true}')]);
    });

    test('concatène plusieurs lignes data: séparées par \\n', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: update\ndata: {"a":1}\ndata: {"b":2}\n\n');
      expect(events.single.data, '{"a":1}\n{"b":2}');
    });

    test('ignore les lignes commentaires (ping `:`)', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed(': ping\n\n');
      parser.feed('event: foo\ndata: bar\n\n');
      expect(events, [SseEvent(event: 'foo', data: 'bar')]);
    });

    test('event sans type explicite → event="message"', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('data: hello\n\n');
      expect(events.single.event, 'message');
    });

    test('supporte les chunks coupés au milieu d\'une ligne', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: up');
      parser.feed('date\ndata: x');
      parser.feed('\n\n');
      expect(events.single, SseEvent(event: 'update', data: 'x'));
    });
  });
}
