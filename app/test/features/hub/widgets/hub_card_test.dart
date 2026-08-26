import 'package:astro_brain/features/hub/widgets/hub_card.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

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

Widget _wrap(Widget child) => MaterialApp(
      theme: _testTheme(),
      home: Scaffold(body: child),
    );

void main() {
  testWidgets('HubCard renders label, hint and hero icon', (tester) async {
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedTelescope01,
        label: 'SETUP',
        hint: 'Site · réseau · almanach',
        onTap: () {},
      ),
    ));

    expect(find.text('SETUP'), findsOneWidget);
    expect(find.text('Site · réseau · almanach'), findsOneWidget);
    expect(
      find.byWidgetPredicate(
        (w) =>
            w is HugeIcon &&
            identical(w.icon, HugeIcons.strokeRoundedTelescope01),
      ),
      findsOneWidget,
    );
  });

  testWidgets('HubCard onTap is invoked', (tester) async {
    var taps = 0;
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedTelescope01,
        label: 'SETUP',
        hint: 'hint',
        onTap: () => taps++,
      ),
    ));

    await tester.tap(find.byType(HubCard));
    await tester.pumpAndSettle();

    expect(taps, 1);
  });

  testWidgets('HubCard primary variant shows chevron icon', (tester) async {
    await tester.pumpWidget(_wrap(
      HubCard(
        heroIcon: HugeIcons.strokeRoundedJoystick01,
        label: 'MANUEL',
        hint: 'Joystick',
        primary: true,
        onTap: () {},
      ),
    ));

    expect(
      find.byWidgetPredicate(
          (w) => w is PhosphorIcon && w.icon == PhosphorIconsBold.caretRight),
      findsOneWidget,
    );
  });
}
