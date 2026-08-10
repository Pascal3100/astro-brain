import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import '_fixtures.dart';

void main() {
  test('FixedObjectProvider : filtres kind/max_mag/messier/search + tri', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'NGC1976', kind: 'dso', name: 'Orion Nebula',
        ra: 83.8, dec: -5.4, mag: 4.0, messier: 'M42', ngcIc: 'NGC1976');
    insertFixed(db, id: 'star:HIP32349', kind: 'star', name: 'Sirius',
        ra: 101.3, dec: -16.7, mag: -1.46);
    insertFixed(db, id: 'NGC7000', kind: 'dso', name: 'North America',
        ra: 314.0, dec: 44.0, mag: null);
    final ref = LocalReferenceDb.withDatabase(db);
    final p = FixedObjectProvider(ref);

    final all = p.listObjects(const LocalCatalogFilter());
    expect(all.map((o) => o.name),
        ['Sirius', 'Orion Nebula', 'North America']); // mag asc, null en dernier

    final messier = p.listObjects(const LocalCatalogFilter(messierOnly: true));
    expect(messier.map((o) => o.qualifiedId), ['NGC1976']);

    final dso = p.listObjects(const LocalCatalogFilter(kind: 'dso', maxMag: 5));
    expect(dso.map((o) => o.name), ['Orion Nebula']);

    final search = p.listObjects(const LocalCatalogFilter(search: 'siri'));
    expect(search.single.name, 'Sirius');
    ref.close();
  });

  test('EphemerisProvider : interpole dans la fenêtre, exclut les stale', () {
    final db = newReferenceDb();
    insertEphemObject(db, id: 'planet:mars', kind: 'planet', name: 'Mars');
    insertEphemSample(db, id: 'planet:mars',
        sampleUtc: '2026-08-10T00:00:00+00:00', ra: 100.0, dec: 10.0, mag: 0.5);
    insertEphemSample(db, id: 'planet:mars',
        sampleUtc: '2026-08-11T00:00:00+00:00', ra: 102.0, dec: 12.0, mag: 0.5);
    // objet hors fenêtre → stale → exclu de listObjects
    insertEphemObject(db, id: 'comet:X', kind: 'comet', name: 'Comet X');
    insertEphemSample(db, id: 'comet:X',
        sampleUtc: '2026-01-01T00:00:00+00:00', ra: 5.0, dec: 5.0, mag: 8.0);
    final ref = LocalReferenceDb.withDatabase(db);
    final p = EphemerisProvider(ref,
        nowUtc: () => DateTime.utc(2026, 8, 10, 12));

    final objs = p.listObjects(const LocalCatalogFilter());
    expect(objs.map((o) => o.qualifiedId), ['planet:mars']);
    expect(objs.single.raDeg, closeTo(101.0, 1e-9)); // interpolé au milieu
    expect(objs.single.ephemerisStale, isFalse);
    ref.close();
  });
}
