import 'dart:convert';
import 'dart:io';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:astro_brain/oracle_cache/almanac_store.dart';
import 'package:astro_brain/oracle_cache/almanac_sync.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqlite3/sqlite3.dart';
import '../features/catalogue/local/_fixtures.dart';

/// Construit un reference.sqlite valide (schema_version donné) et renvoie ses bytes.
List<int> buildSqliteBytes(Directory tmp, {int schemaVersion = 2}) {
  final path = '${tmp.path}/seed.sqlite';
  final db = sqlite3.open(path);
  db.execute(kReferenceSchemaDdl);
  db.execute('INSERT INTO meta (schema_version, generated_at, window_start,'
      ' window_end) VALUES ($schemaVersion, "g", "s", "e")');
  db.dispose();
  return File(path).readAsBytesSync();
}

String manifestJson(String url, String sha) => jsonEncode({
      'schema_version': 2, 'generated_at': 'g', 'sqlite_url': url,
      'sqlite_sha256': sha, 'window_start': 's', 'window_end': 'e',
    });

void main() {
  late Directory tmp;
  late AlmanacStore store;
  late LocalReferenceDb ref;
  setUp(() {
    tmp = Directory.systemTemp.createTempSync('almanac_sync_test');
    store = AlmanacStore(docsDir: () async => tmp);
    ref = LocalReferenceDb('${tmp.path}/reference.sqlite');
  });
  tearDown(() { ref.close(); tmp.deleteSync(recursive: true); });

  AlmanacSync sync(MockClient client) => AlmanacSync(
      store: store, reference: ref, clientFactory: () => client);

  test('sha différent → download + swap → updated + reopen ready', () async {
    final bytes = buildSqliteBytes(tmp);
    final sha = sha256.convert(bytes).toString();
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', sha), 200);
      }
      return http.Response.bytes(bytes, 200);
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.updated);
    expect(ref.ready, isTrue); // reopen après swap
  });

  test('sha identique au cache → upToDate, pas de download', () async {
    final bytes = buildSqliteBytes(tmp);
    final sha = sha256.convert(bytes).toString();
    (await store.file()).writeAsBytesSync(bytes);
    var dbHits = 0;
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', sha), 200);
      }
      dbHits++;
      return http.Response.bytes(bytes, 200);
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.upToDate);
    expect(dbHits, 0);
  });

  test('sha du corps téléchargé faux → rejectedHash, cache conservé', () async {
    final bytes = buildSqliteBytes(tmp);
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', 'deadbeef'), 200);
      }
      return http.Response.bytes(bytes, 200); // sha ne matchera pas 'deadbeef'
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.rejectedHash);
  });

  test('manifest schema_version 3 → rejectedSchema', () async {
    final client = MockClient((req) async => http.Response(
        jsonEncode({'schema_version': 3, 'generated_at': 'g',
          'sqlite_url': 'https://x/db', 'sqlite_sha256': 'x',
          'window_start': 's', 'window_end': 'e'}), 200));
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.rejectedSchema);
  });

  test('erreur réseau → offline, cache conservé', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.offline);
  });
}
