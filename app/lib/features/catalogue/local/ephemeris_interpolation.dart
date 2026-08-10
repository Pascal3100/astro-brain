/// Interpolation linéaire pure des éphémères — port de
/// `backend/astro_brain/services/catalog/interpolation.py`.
library;

/// Parse un ISO-8601 en `DateTime` UTC. Suffixe `Z` accepté. Une chaîne
/// SANS offset est interprétée comme UTC (comme le backend), pas comme
/// heure locale — d'où l'ajout de `Z` avant `DateTime.parse`, qui sinon
/// lirait une date naïve en heure locale.
DateTime parseUtc(String s) {
  if (s.endsWith('Z')) return DateTime.parse(s).toUtc();
  final hasOffset = RegExp(r'[+\-]\d{2}:?\d{2}$').hasMatch(s);
  if (hasOffset) return DateTime.parse(s).toUtc();
  return DateTime.parse('${s}Z').toUtc();
}

double lerp(double a, double b, double frac) => a + (b - a) * frac;

/// Interpole un angle (deg) sur le plus court arc ; résultat dans [0, 360).
double lerpAngleDeg(double a, double b, double frac) {
  final diff = ((b - a + 180.0) % 360.0) - 180.0;
  return (a + diff * frac) % 360.0;
}

/// Interpole (ra, dec) à `t` entre deux échantillons `(utc, ra, dec)`.
({double ra, double dec}) interpolateRaDec(
  (DateTime, double, double) before,
  (DateTime, double, double) after,
  DateTime t,
) {
  final (t0, ra0, dec0) = before;
  final (t1, ra1, dec1) = after;
  final span = t1.difference(t0).inMicroseconds.toDouble();
  if (span == 0) return (ra: ra0 % 360.0, dec: dec0);
  var frac = t.difference(t0).inMicroseconds.toDouble() / span;
  frac = frac.clamp(0.0, 1.0);
  return (ra: lerpAngleDeg(ra0, ra1, frac), dec: lerp(dec0, dec1, frac));
}
