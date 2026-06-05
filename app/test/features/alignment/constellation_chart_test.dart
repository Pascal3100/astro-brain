import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/widgets/constellation_chart.dart';

ConstellationFigureDto _fig({required bool oriented}) => ConstellationFigureDto(
      abbr: 'UMa', name: 'Grande Ourse', oriented: oriented,
      nodes: [
        ConstellationNodeDto(label: 'Dubhe', mag: 1.79, raDeg: 165.9,
            decDeg: 61.7, az: oriented ? 312.0 : null,
            alt: oriented ? 47.0 : null, isTarget: true),
        ConstellationNodeDto(label: 'Merak', mag: 2.37, raDeg: 165.4,
            decDeg: 56.3, az: oriented ? 310.0 : null,
            alt: oriented ? 42.0 : null, isTarget: false),
      ],
      segments: const [[0, 1]],
    );

void main() {
  testWidgets('renders oriented figure with target label', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ConstellationChart(figure: _fig(oriented: true))),
    ));
    expect(find.text('Dubhe'), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
  });

  testWidgets('falls back to atlas projection when not oriented',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ConstellationChart(figure: _fig(oriented: false))),
    ));
    expect(find.textContaining('orienté'), findsNothing);
  });
}
