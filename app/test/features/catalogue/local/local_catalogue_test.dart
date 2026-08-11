import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_catalogue.dart';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import '_fixtures.dart';

void main() {
  LocalCatalogue build(LocalReferenceDb ref) => LocalCatalogue(
        reference: ref,
        fixed: FixedObjectProvider(ref),
        ephemeris: EphemerisProvider(ref, nowUtc: () => DateTime.utc(2026, 8, 10, 12)),
      );

  test('merge fixe + éphémère trié par magnitude', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'star:HIP32349', kind: 'star', name: 'Sirius',
        ra: 101.3, dec: -16.7, mag: -1.46);
    insertEphemObject(db, id: 'planet:venus', kind: 'planet', name: 'Venus');
    insertEphemSample(db, id: 'planet:venus',
        sampleUtc: '2026-08-10T00:00:00+00:00', ra: 50.0, dec: 5.0, mag: -4.0);
    insertEphemSample(db, id: 'planet:venus',
        sampleUtc: '2026-08-11T00:00:00+00:00', ra: 52.0, dec: 6.0, mag: -4.0);
    final ref = LocalReferenceDb.withDatabase(db);
    final objs = build(ref).listAll(const LocalCatalogFilter());
    expect(objs.map((o) => o.name), ['Venus', 'Sirius']); // -4.0 avant -1.46
    ref.close();
  });

  test('kind fixe → délègue au provider fixe uniquement', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'NGC1976', kind: 'dso', name: 'Orion', ra: 83.8, dec: -5.4, mag: 4.0);
    insertEphemObject(db, id: 'planet:mars', kind: 'planet', name: 'Mars');
    insertEphemSample(db, id: 'planet:mars', sampleUtc: '2026-08-10T00:00:00+00:00', ra: 100.0, dec: 10.0, mag: 0.5);
    insertEphemSample(db, id: 'planet:mars', sampleUtc: '2026-08-11T00:00:00+00:00', ra: 102.0, dec: 12.0, mag: 0.5);
    final ref = LocalReferenceDb.withDatabase(db);
    final objs = build(ref).listAll(const LocalCatalogFilter(kind: 'dso'));
    expect(objs.map((o) => o.qualifiedId), ['NGC1976']);
    ref.close();
  });

  test('!ready → liste vide', () {
    final ref = LocalReferenceDb('/nope/reference.sqlite')..open();
    expect(build(ref).listAll(const LocalCatalogFilter()), isEmpty);
  });
}
