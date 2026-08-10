import 'package:astro_brain/features/alignment/phone_location.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/local/visibility.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeLoc implements PhoneLocation {
  _FakeLoc(this._fix);
  final ({double lat, double lon})? _fix;
  @override
  Future<({double lat, double lon})?> current() async => _fix;
}

CatalogObjectDto obj(String id, {double ra = 279.23, double dec = 38.78, bool stale = false}) =>
    CatalogObjectDto(qualifiedId: id, kind: 'star', name: id, raDeg: ra, decDeg: dec, ephemerisStale: stale);

void main() {
  DateTime clock() => DateTime.utc(2026, 8, 10, 22);

  test('sans fix GPS : objets intacts, filtre ignoré', () async {
    final v = Visibility(location: _FakeLoc(null), clock: clock);
    final out = await v.enrich([obj('a')], visibleNow: true);
    expect(out.single.altitudeDeg, isNull);
  });

  test('stale exclu si visibleNow, gardé sinon', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    expect(await v.enrich([obj('s', stale: true)], visibleNow: true), isEmpty);
    final kept = await v.enrich([obj('s', stale: true)], visibleNow: false);
    expect(kept.single.altitudeDeg, isNull); // jamais enrichi
  });

  test('objet sous l\'horizon exclu si visibleNow', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    // objet au pôle sud céleste : sous l'horizon depuis lat +43.6
    final out = await v.enrich([obj('south', ra: 0, dec: -89)], visibleNow: true);
    expect(out, isEmpty);
  });

  test('objet au-dessus de l\'horizon : alt/az renseignés', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    final out = await v.enrich([obj('north', ra: 0, dec: 80)], visibleNow: true);
    expect(out.single.altitudeDeg, isNotNull);
    expect(out.single.azimuthDeg, isNotNull);
  });
}
