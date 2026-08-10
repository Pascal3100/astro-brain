/// Handle lecture seule vers un `reference.sqlite` local — port de
/// `backend/astro_brain/repository/reference_db.py`. `sqlite3` étant synchrone
/// (pas de requête en vol pendant un reopen), on simplifie : pas de handle
/// « stale » différé, un close + open direct.
library;

import 'package:flutter/foundation.dart';
import 'package:sqlite3/sqlite3.dart';

import '../../../oracle_cache/almanac_store.dart' show kSupportedSchemaVersion;

class ReferenceMetaLocal {
  const ReferenceMetaLocal({
    required this.schemaVersion,
    required this.generatedAt,
    required this.windowStart,
    required this.windowEnd,
  });
  final int schemaVersion;
  final String generatedAt;
  final String windowStart;
  final String windowEnd;
}

class LocalReferenceDb {
  LocalReferenceDb(this._path);

  @visibleForTesting
  LocalReferenceDb.withDatabase(Database db) : _path = ':memory:' {
    _adopt(db);
  }

  final String _path;
  Database? _conn;

  bool get ready => _conn != null;
  Database? current() => _conn;

  void open() {
    _conn?.dispose();
    _conn = null;
    Database db;
    try {
      db = sqlite3.open(_path, mode: OpenMode.readOnly);
    } on SqliteException {
      return; // fichier absent / verrouillé / corrompu → !ready
    }
    _adopt(db);
  }

  void reopen() => open();

  void _adopt(Database db) {
    try {
      final row = db.select('SELECT schema_version FROM meta LIMIT 1');
      if (row.isEmpty || (row.first['schema_version'] as int) > kSupportedSchemaVersion) {
        db.dispose();
        return;
      }
    } on SqliteException {
      db.dispose();
      return;
    }
    _conn = db;
  }

  ReferenceMetaLocal? meta() {
    final conn = _conn;
    if (conn == null) return null;
    final rows = conn.select(
      'SELECT schema_version, generated_at, window_start, window_end'
      ' FROM meta LIMIT 1');
    if (rows.isEmpty) return null;
    final r = rows.first;
    return ReferenceMetaLocal(
      schemaVersion: r['schema_version'] as int,
      generatedAt: r['generated_at'] as String,
      windowStart: r['window_start'] as String,
      windowEnd: r['window_end'] as String,
    );
  }

  void close() {
    _conn?.dispose();
    _conn = null;
  }
}
