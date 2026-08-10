import 'package:astro_brain/features/catalogue/widgets/solar_warning_dialog.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _theme() {
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
  testWidgets('confirmer retourne true', (tester) async {
    late Future<bool> result;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Builder(
        builder: (ctx) => ElevatedButton(
          onPressed: () => result = showSolarWarningDialog(ctx),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Soleil'), findsWidgets);
    await tester.tap(find.text('POINTER QUAND MÊME'));
    await tester.pumpAndSettle();
    expect(await result, isTrue);
  });

  testWidgets('annuler retourne false', (tester) async {
    late Future<bool> result;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Builder(
        builder: (ctx) => ElevatedButton(
          onPressed: () => result = showSolarWarningDialog(ctx),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ANNULER'));
    await tester.pumpAndSettle();
    expect(await result, isFalse);
  });
}
