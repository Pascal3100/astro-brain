import 'package:flutter_test/flutter_test.dart';
import 'package:astro_brain/features/alignment/alignment_models.dart';

void main() {
  test('ConstellationFigureDto.fromJson parses nodes and segments', () {
    final dto = ConstellationFigureDto.fromJson({
      'abbr': 'UMa',
      'name': 'Grande Ourse',
      'oriented': true,
      'nodes': [
        {
          'label': 'Dubhe',
          'mag': 1.79,
          'ra_deg': 165.9,
          'dec_deg': 61.7,
          'az': 312.4,
          'alt': 47.1,
          'is_target': true,
        },
        {
          'label': 'Merak',
          'mag': 2.37,
          'ra_deg': 165.4,
          'dec_deg': 56.3,
          'az': 310.0,
          'alt': 42.0,
          'is_target': false,
        },
      ],
      'segments': [
        [0, 1]
      ],
    });
    expect(dto.name, 'Grande Ourse');
    expect(dto.oriented, isTrue);
    expect(dto.nodes.length, 2);
    expect(dto.nodes.first.isTarget, isTrue);
    expect(dto.segments.first, [0, 1]);
  });

  test('ConstellationNodeDto handles null az/alt (not oriented)', () {
    final node = ConstellationNodeDto.fromJson({
      'label': 'X',
      'mag': 2.0,
      'ra_deg': 10.0,
      'dec_deg': 20.0,
      'az': null,
      'alt': null,
      'is_target': false,
    });
    expect(node.az, isNull);
    expect(node.alt, isNull);
  });
}
