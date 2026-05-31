import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/widgets/catalogue_object_card.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _testTheme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

void main() {
  testWidgets('renders name, mag and tapping fires onTap', (tester) async {
    var tapped = false;
    await tester.pumpWidget(MaterialApp(
      theme: _testTheme(),
      home: Scaffold(
        body: CatalogueObjectCard(
          object: const CatalogObjectDto(
            qualifiedId: 'star:sirius',
            kind: 'star',
            name: 'Sirius',
            designation: 'alpha CMa',
            raDeg: 101.0,
            decDeg: -16.0,
            mag: -1.45,
            constellation: 'CMa',
            altitudeDeg: 34.0,
            azimuthDeg: 168.0,
          ),
          onTap: () => tapped = true,
        ),
      ),
    ));
    expect(find.text('Sirius'), findsOneWidget);
    expect(find.textContaining('-1.4'), findsWidgets);
    await tester.tap(find.byType(CatalogueObjectCard));
    expect(tapped, isTrue);
  });
}
