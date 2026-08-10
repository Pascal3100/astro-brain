import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('CatalogObjectDto.fromJson parses fields incl. alt/az', () {
    final dto = CatalogObjectDto.fromJson({
      'qualified_id': 'star:sirius',
      'kind': 'star',
      'name': 'Sirius',
      'designation': 'alpha CMa',
      'ra_deg': 101.287,
      'dec_deg': -16.716,
      'mag': -1.45,
      'constellation': 'CMa',
      'object_type': 'star',
      'altitude_deg': 34.0,
      'azimuth_deg': 168.0,
    });
    expect(dto.qualifiedId, 'star:sirius');
    expect(dto.name, 'Sirius');
    expect(dto.mag, -1.45);
    expect(dto.altitudeDeg, 34.0);
    expect(dto.isVisible, isTrue);
  });

  test('isVisible false when altitude null or <= 0', () {
    final dto = CatalogObjectDto.fromJson({
      'qualified_id': 'star:x', 'kind': 'star', 'name': 'X',
      'ra_deg': 0.0, 'dec_deg': 0.0,
    });
    expect(dto.altitudeDeg, isNull);
    expect(dto.isVisible, isFalse);
  });

  test('fromJson lit les champs v2 (messier/ngc_ic/illumination/size/stale)',
      () {
    final o = CatalogObjectDto.fromJson({
      'qualified_id': 'dso:m31',
      'kind': 'dso',
      'name': 'Andromède',
      'ra_deg': 10.68,
      'dec_deg': 41.27,
      'mag': 3.4,
      'object_type': 'galaxy',
      'angular_size_arcmin': 190.0,
      'messier': 'M31',
      'ngc_ic': 'NGC 224',
      'illumination': null,
      'ephemeris_stale': false,
    });
    expect(o.messier, 'M31');
    expect(o.ngcIc, 'NGC 224');
    expect(o.angularSizeArcmin, 190.0);
    expect(o.illumination, isNull);
    expect(o.ephemerisStale, isFalse);
  });

  test('fromJson : ephemeris_stale absent → false ; moon illumination', () {
    final o = CatalogObjectDto.fromJson({
      'qualified_id': 'moon:moon',
      'kind': 'moon',
      'name': 'Lune',
      'ra_deg': 200.0,
      'dec_deg': -10.0,
      'illumination': 0.42,
    });
    expect(o.ephemerisStale, isFalse);
    expect(o.illumination, 0.42);
  });
}
