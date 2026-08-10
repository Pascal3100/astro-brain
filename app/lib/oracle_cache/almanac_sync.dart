/// Sync de reference.sqlite : fetch conditionnel (sha256), verify, swap
/// atomique. Miroir de `backend/astro_brain/services/reference/sync.py`.
/// Non bloquant : toute erreur réseau garde le cache courant (offline).
library;

import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'package:sqlite3/sqlite3.dart';

import '../features/catalogue/local/local_reference_db.dart';
import 'almanac_store.dart';
import 'manifest_dto.dart';

enum AlmanacSyncStatus { updated, upToDate, offline, rejectedSchema, rejectedHash }

class AlmanacSyncResult {
  const AlmanacSyncResult(this.status, {this.schemaVersion});
  final AlmanacSyncStatus status;
  final int? schemaVersion;
}

class AlmanacSync {
  AlmanacSync({
    required AlmanacStore store,
    required LocalReferenceDb reference,
    http.Client Function()? clientFactory,
    this.manifestUrl = kManifestUrl,
  })  : _store = store,
        _reference = reference,
        _clientFactory = clientFactory ?? http.Client.new;

  final AlmanacStore _store;
  final LocalReferenceDb _reference;
  final http.Client Function() _clientFactory;
  final String manifestUrl;

  Future<AlmanacSyncResult> sync() async {
    final client = _clientFactory();
    List<int> data;
    AlmanacManifest manifest;
    try {
      final resp = await client.get(Uri.parse(manifestUrl));
      if (resp.statusCode != 200) return const AlmanacSyncResult(AlmanacSyncStatus.offline);
      final decoded = jsonDecode(resp.body);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('manifest: corps JSON non objet');
      }
      manifest = AlmanacManifest.fromJson(decoded);
      if (manifest.schemaVersion > kSupportedSchemaVersion) {
        return AlmanacSyncResult(AlmanacSyncStatus.rejectedSchema,
            schemaVersion: manifest.schemaVersion);
      }
      if (await _store.localSha256() == manifest.sqliteSha256) {
        return AlmanacSyncResult(AlmanacSyncStatus.upToDate,
            schemaVersion: manifest.schemaVersion);
      }
      final dl = await client.get(Uri.parse(manifest.sqliteUrl));
      if (dl.statusCode != 200) return const AlmanacSyncResult(AlmanacSyncStatus.offline);
      data = dl.bodyBytes;
    } on Exception {
      return const AlmanacSyncResult(AlmanacSyncStatus.offline);
    } finally {
      client.close();
    }

    if (sha256.convert(data).toString() != manifest.sqliteSha256) {
      return const AlmanacSyncResult(AlmanacSyncStatus.rejectedHash);
    }

    final tmp = await _store.tmpFile();
    tmp.writeAsBytesSync(data);
    final tmpSv = _schemaVersionOf(tmp.path);
    if (tmpSv == null || tmpSv > kSupportedSchemaVersion) {
      if (tmp.existsSync()) tmp.deleteSync();
      return AlmanacSyncResult(AlmanacSyncStatus.rejectedSchema, schemaVersion: tmpSv);
    }
    final dest = await _store.file();
    tmp.renameSync(dest.path); // swap atomique (même FS)
    _reference.reopen();
    return AlmanacSyncResult(AlmanacSyncStatus.updated,
        schemaVersion: manifest.schemaVersion);
  }

  int? _schemaVersionOf(String path) {
    Database db;
    try {
      db = sqlite3.open(path, mode: OpenMode.readOnly);
    } on SqliteException {
      return null;
    }
    try {
      final rows = db.select('SELECT schema_version FROM meta LIMIT 1');
      return rows.isEmpty ? null : rows.first['schema_version'] as int;
    } on SqliteException {
      return null;
    } finally {
      db.dispose();
    }
  }
}
