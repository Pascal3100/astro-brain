/// Enrichissement de visibilité local — port de
/// `backend/astro_brain/services/catalog/visibility.py`. GPS via PhoneLocation.
library;

import '../../alignment/phone_location.dart';
import '../catalogue_models.dart';
import 'sky_projection.dart';

const kMinVisibleAltDeg = 0.0;

class Visibility {
  Visibility({required PhoneLocation location, DateTime Function()? clock})
      : _location = location,
        _clock = clock ?? (() => DateTime.now().toUtc());

  final PhoneLocation _location;
  final DateTime Function() _clock;

  Future<List<CatalogObjectDto>> enrich(
    List<CatalogObjectDto> objects, {
    required bool visibleNow,
  }) async {
    final fix = await _location.current();
    if (fix == null) return objects; // pas de position : filtre ignoré
    final observer = Observer(latDeg: fix.lat, lonDeg: fix.lon);
    final t = _clock();
    final out = <CatalogObjectDto>[];
    for (final obj in objects) {
      if (obj.ephemerisStale) {
        if (visibleNow) continue;
        out.add(obj);
        continue;
      }
      final r = skyAzAltFromRaDec(obj.raDeg, obj.decDeg, observer, t);
      if (visibleNow && r.alt <= kMinVisibleAltDeg) continue;
      out.add(obj.copyWith(altitudeDeg: r.alt, azimuthDeg: r.az));
    }
    return out;
  }
}
