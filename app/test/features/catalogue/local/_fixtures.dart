import 'package:sqlite3/sqlite3.dart';

/// DDL copié de oracle/schema.sql (schema_version 2).
const kReferenceSchemaDdl = '''
CREATE TABLE meta (
  schema_version INTEGER NOT NULL, generated_at TEXT NOT NULL, mpc_epoch TEXT,
  window_start TEXT NOT NULL, window_end TEXT NOT NULL, skyfield_kernel TEXT);
CREATE TABLE objects (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, designation TEXT);
CREATE TABLE fixed_object (
  object_id TEXT PRIMARY KEY REFERENCES objects(id), ra_deg REAL NOT NULL,
  dec_deg REAL NOT NULL, apparent_mag REAL, object_type TEXT, size_arcmin REAL,
  constellation TEXT, messier TEXT, ngc_ic TEXT);
CREATE TABLE ephemeris (
  object_id TEXT NOT NULL REFERENCES objects(id), sample_utc TEXT NOT NULL,
  ra_deg REAL NOT NULL, dec_deg REAL NOT NULL, earth_dist_au REAL,
  sun_dist_au REAL, apparent_mag REAL, illumination REAL, constellation TEXT,
  PRIMARY KEY (object_id, sample_utc));
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);
CREATE TABLE comet_elements (
  object_id TEXT PRIMARY KEY REFERENCES objects(id), epoch_jd REAL,
  perihelion_q_au REAL NOT NULL, eccentricity REAL NOT NULL,
  inclination_deg REAL NOT NULL, arg_perihelion_deg REAL NOT NULL,
  node_deg REAL NOT NULL, mag_h REAL, mag_k REAL);
''';

Database newReferenceDb({int schemaVersion = 2}) {
  final db = sqlite3.openInMemory();
  db.execute(kReferenceSchemaDdl);
  db.execute(
    'INSERT INTO meta (schema_version, generated_at, window_start, window_end,'
    ' skyfield_kernel) VALUES (?, ?, ?, ?, ?)',
    [schemaVersion, '2026-08-10T00:00:00+00:00', '2026-08-01', '2026-09-30',
     'de421.bsp'],
  );
  return db;
}

void insertFixed(Database db, {
  required String id, required String kind, String? name, String? designation,
  required double ra, required double dec, double? mag, String? objectType,
  double? sizeArcmin, String? constellation, String? messier, String? ngcIc,
}) {
  db.execute('INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)',
      [id, kind, name, designation]);
  db.execute(
    'INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag,'
    ' object_type, size_arcmin, constellation, messier, ngc_ic)'
    ' VALUES (?,?,?,?,?,?,?,?,?)',
    [id, ra, dec, mag, objectType, sizeArcmin, constellation, messier, ngcIc]);
}

void insertEphemObject(Database db, {
  required String id, required String kind, String? name, String? designation,
}) {
  db.execute('INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)',
      [id, kind, name, designation]);
}

void insertEphemSample(Database db, {
  required String id, required String sampleUtc, required double ra,
  required double dec, double? mag, double? illumination, String? constellation,
}) {
  db.execute(
    'INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg,'
    ' apparent_mag, illumination, constellation) VALUES (?,?,?,?,?,?,?)',
    [id, sampleUtc, ra, dec, mag, illumination, constellation]);
}
