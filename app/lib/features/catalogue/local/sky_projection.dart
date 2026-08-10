/// Projection pure RA/Dec (of-date) → Az/Alt apparent — port de
/// `backend/astro_brain/services/_ephemeris.py`. Précision arc-min, sans
/// nutation/aberration/réfraction. Az depuis le Nord vers l'Est ; Alt depuis
/// l'horizon. `t` en argument : le même moteur sert « maintenant » (SP3-B) et
/// une date/heure arbitraire (SP3-C).
library;

import 'dart:math' as math;

class Observer {
  const Observer({required this.latDeg, required this.lonDeg});
  final double latDeg;
  final double lonDeg;
}

double _rad(double d) => d * math.pi / 180.0;
double _deg(double r) => r * 180.0 / math.pi;

double julianDate(DateTime tUtc) {
  final t = tUtc.toUtc();
  var y = t.year;
  var m = t.month;
  final d = t.day + (t.hour + (t.minute + t.second / 60.0) / 60.0) / 24.0;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  final a = y ~/ 100;
  final b = 2 - a + a ~/ 4;
  return (365.25 * (y + 4716)).floorToDouble() +
      (30.6001 * (m + 1)).floorToDouble() +
      d +
      b -
      1524.5;
}

/// Greenwich Mean Sidereal Time en degrés (IAU 1982). `T₀` à 0h UT du jour,
/// heure UT ajoutée séparément via `1.00273790935·H` (les mélanger induit
/// ~0.5° de biais).
double gmstDeg(DateTime tUtc) {
  final jd = julianDate(tUtc);
  final jd0 = (jd - 0.5).floorToDouble() + 0.5;
  final hUt = (jd - jd0) * 24.0;
  final t0 = (jd0 - 2451545.0) / 36525.0;
  final gmstH = 6.697374558 +
      2400.051336 * t0 +
      0.000025862 * t0 * t0 +
      1.00273790935 * hUt;
  return (gmstH * 15.0) % 360.0;
}

({double az, double alt}) skyAzAltFromRaDec(
    double raDeg, double decDeg, Observer o, DateTime tUtc) {
  final gmst = gmstDeg(tUtc);
  final lst = (gmst + o.lonDeg) % 360.0;
  var haDeg = (lst - raDeg) % 360.0;
  if (haDeg > 180) haDeg -= 360;
  final ha = _rad(haDeg);
  final dec = _rad(decDeg);
  final lat = _rad(o.latDeg);

  final sinAlt =
      (math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(ha))
          .clamp(-1.0, 1.0);
  final alt = _deg(math.asin(sinAlt));
  final altRad = _rad(alt);

  final sinAz = -math.cos(dec) * math.sin(ha) / math.cos(altRad);
  final cosAz = (math.sin(dec) - math.sin(altRad) * math.sin(lat)) /
      (math.cos(altRad) * math.cos(lat));
  final az = _deg(math.atan2(sinAz, cosAz)) % 360.0;
  return (az: az, alt: alt);
}
