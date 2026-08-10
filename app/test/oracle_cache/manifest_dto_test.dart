import 'package:astro_brain/oracle_cache/manifest_dto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final json = {
    'schema_version': 2,
    'generated_at': '2026-08-10T00:00:00+00:00',
    'sqlite_url': 'https://example/reference.sqlite',
    'sqlite_sha256': 'abc123',
    'window_start': '2026-08-01',
    'window_end': '2026-09-30',
  };

  test('fromJson parse toutes les clés', () {
    final m = AlmanacManifest.fromJson(json);
    expect(m.schemaVersion, 2);
    expect(m.sqliteUrl, 'https://example/reference.sqlite');
    expect(m.sqliteSha256, 'abc123');
    expect(m.windowEnd, '2026-09-30');
  });

  test('fromJson lève FormatException si clé requise absente', () {
    final bad = Map<String, dynamic>.from(json)..remove('sqlite_sha256');
    expect(() => AlmanacManifest.fromJson(bad), throwsFormatException);
  });
}
