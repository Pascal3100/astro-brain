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
}
