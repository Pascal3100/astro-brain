import 'package:astro_brain/features/catalogue/local/ephemeris_interpolation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parseUtc : offset explicite et naïf interprété UTC', () {
    expect(parseUtc('2026-08-10T00:00:00+00:00').toUtc().hour, 0);
    expect(parseUtc('2026-08-10T06:00:00Z').toUtc().hour, 6);
    // naïf → traité comme UTC (comme le backend), pas comme heure locale
    expect(parseUtc('2026-08-10T06:00:00').toUtc().hour, 6);
  });

  test('lerp linéaire', () {
    expect(lerp(10, 20, 0.25), closeTo(12.5, 1e-9));
  });

  test('lerpAngleDeg prend le plus court arc et wrappe 359->1', () {
    expect(lerpAngleDeg(359, 1, 0.5), closeTo(0.0, 1e-9));
    expect(lerpAngleDeg(10, 20, 0.5), closeTo(15.0, 1e-9));
  });

  test('interpolateRaDec : milieu de segment', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final t1 = DateTime.utc(2026, 8, 11, 0);
    final t = DateTime.utc(2026, 8, 10, 12);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t1, 102.0, 12.0), t);
    expect(r.ra, closeTo(101.0, 1e-9));
    expect(r.dec, closeTo(11.0, 1e-9));
  });

  test('interpolateRaDec : span nul renvoie l\'échantillon before', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t0, 200.0, 20.0), t0);
    expect(r.ra, closeTo(100.0, 1e-9));
    expect(r.dec, closeTo(10.0, 1e-9));
  });

  test('interpolateRaDec : frac clampé hors bornes', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final t1 = DateTime.utc(2026, 8, 11, 0);
    final tBefore = DateTime.utc(2026, 8, 9, 0);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t1, 102.0, 12.0), tBefore);
    expect(r.ra, closeTo(100.0, 1e-9)); // frac=0
    expect(r.dec, closeTo(10.0, 1e-9));
  });
}
