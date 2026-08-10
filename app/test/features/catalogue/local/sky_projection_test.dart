import 'package:astro_brain/features/catalogue/local/sky_projection.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final t = DateTime.utc(2026, 8, 10, 22, 0, 0);
  const o = Observer(latDeg: 43.6, lonDeg: 1.44);

  test('gmstDeg == backend', () {
    expect(gmstDeg(t), closeTo(289.39243412523683, 1e-6));
  });

  test('skyAzAltFromRaDec == backend (Vega)', () {
    final r = skyAzAltFromRaDec(279.23, 38.78, o, t);
    expect(r.az, closeTo(245.0206616167144, 1e-6));
    expect(r.alt, closeTo(80.03986047634285, 1e-6));
  });

  test('proche du pôle : alt ~ lat, pas de NaN (clamp sin_alt)', () {
    final r = skyAzAltFromRaDec(0.0, 89.0, o, t);
    expect(r.alt, closeTo(43.94831836851426, 1e-6));
    expect(r.alt.isNaN, isFalse);
  });

  test('objet bas (Sirius) == backend', () {
    final r = skyAzAltFromRaDec(101.29, -16.7, o, t);
    expect(r.az, closeTo(19.70725551457322, 1e-6));
    expect(r.alt, closeTo(-61.90888093560371, 1e-6));
  });
}
