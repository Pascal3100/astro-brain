/// DTO miroir de `manifest.json` (émis par `oracle/oracle/manifest.py`).
library;

class AlmanacManifest {
  const AlmanacManifest({
    required this.schemaVersion,
    required this.generatedAt,
    required this.sqliteUrl,
    required this.sqliteSha256,
    required this.windowStart,
    required this.windowEnd,
  });

  final int schemaVersion;
  final String generatedAt;
  final String sqliteUrl;
  final String sqliteSha256;
  final String windowStart;
  final String windowEnd;

  factory AlmanacManifest.fromJson(Map<String, dynamic> j) {
    T req<T>(String k) {
      final v = j[k];
      if (v == null) throw FormatException('manifest: clé manquante "$k"');
      return v as T;
    }

    return AlmanacManifest(
      schemaVersion: (req<num>('schema_version')).toInt(),
      generatedAt: req<String>('generated_at'),
      sqliteUrl: req<String>('sqlite_url'),
      sqliteSha256: req<String>('sqlite_sha256'),
      windowStart: req<String>('window_start'),
      windowEnd: req<String>('window_end'),
    );
  }
}
