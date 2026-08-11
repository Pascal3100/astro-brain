import 'dart:io';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';
import '_fixtures.dart';

void main() {
  test('withDatabase : ready + meta lue', () {
    final db = newReferenceDb();
    final ref = LocalReferenceDb.withDatabase(db);
    expect(ref.ready, isTrue);
    final m = ref.meta();
    expect(m!.schemaVersion, 2);
    expect(m.windowEnd, '2026-09-30');
    ref.close();
  });

  test('fichier absent : !ready, meta null', () {
    final ref = LocalReferenceDb('/does/not/exist/reference.sqlite');
    ref.open();
    expect(ref.ready, isFalse);
    expect(ref.meta(), isNull);
  });

  test('schema_version 3 : refusé (!ready)', () {
    final db = newReferenceDb(schemaVersion: 3);
    final ref = LocalReferenceDb.withDatabase(db);
    expect(ref.ready, isFalse);
    ref.close();
  });

  test('open() sur un vrai fichier RO', () {
    final tmp = Directory.systemTemp.createTempSync('ref_db_test');
    final path = '${tmp.path}/reference.sqlite';
    final seed = sqlite3.open(path);
    seed..execute(kReferenceSchemaDdl)
        ..execute('INSERT INTO meta (schema_version, generated_at, window_start,'
            ' window_end) VALUES (2, "g", "s", "e")')
        ..dispose();
    final ref = LocalReferenceDb(path)..open();
    expect(ref.ready, isTrue);
    expect(ref.meta()!.windowStart, 's');
    ref.close();
    tmp.deleteSync(recursive: true);
  });
}
