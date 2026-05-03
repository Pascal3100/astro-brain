import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('defaults when no prefs and no dart-define', () async {
    final prefs = await SharedPreferences.getInstance();
    final host = PiHost.fromPrefs(prefs);
    expect(host.host, 'astro-brain.local');
    expect(host.port, 8000);
  });

  test('prefs override defaults', () async {
    SharedPreferences.setMockInitialValues({
      'astro.host': '192.168.1.42',
      'astro.port': 9000,
    });
    final prefs = await SharedPreferences.getInstance();
    final host = PiHost.fromPrefs(prefs);
    expect(host.host, '192.168.1.42');
    expect(host.port, 9000);
  });

  test('uri builders honor host/port', () {
    const host = PiHost(host: '10.0.0.1', port: 8080);
    expect(host.restUri('/state').toString(), 'http://10.0.0.1:8080/state');
    expect(host.sseUri('/events').toString(), 'http://10.0.0.1:8080/events');
  });
}
