import 'package:astro_brain/features/catalogue/constellations.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps IAU abbreviation to full French name', () {
    expect(constellationFullName('CMa'), 'Grand Chien');
    expect(constellationFullName('Lyr'), 'Lyre');
    expect(constellationFullName('Boo'), 'Bouvier');
    expect(constellationFullName('UMa'), 'Grande Ourse');
  });

  test('case-insensitive fallback', () {
    expect(constellationFullName('cma'), 'Grand Chien');
  });

  test('unknown abbreviation falls back to the abbreviation', () {
    expect(constellationFullName('Xyz'), 'Xyz');
  });

  test('null / empty returns null', () {
    expect(constellationFullName(null), isNull);
    expect(constellationFullName(''), isNull);
  });
}
