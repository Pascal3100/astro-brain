import 'package:astro_brain/features/catalogue/widgets/goto_slew_bar.dart';
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
  testWidgets('shows target name and STOP fires onStop', (tester) async {
    var stopped = false;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Scaffold(
        body: GotoSlewBar(targetName: 'Sirius', onStop: () => stopped = true),
      ),
    ));
    expect(find.textContaining('Sirius'), findsOneWidget);
    await tester.tap(find.textContaining('STOP'));
    expect(stopped, isTrue);
  });
}
