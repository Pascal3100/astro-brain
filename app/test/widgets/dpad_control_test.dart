import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/widgets/dpad_control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// ThemeData minimal portant l'extension AppColors (sans google_fonts).
ThemeData _testTheme() => ThemeData(
      useMaterial3: true,
      extensions: [AppColors.day],
    );

void main() {
  testWidgets('DPadControl invokes onPress with direction on press down',
      (tester) async {
    DPadDirection? lastPress;
    var releases = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: DPadControl(
            onPress: (d) => lastPress = d,
            onRelease: () => releases++,
          ),
        ),
      ),
    );

    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('dpad-up'))),
    );
    expect(lastPress, DPadDirection.up);
    await gesture.up();
    await tester.pump();
    expect(releases, 1);
  });

  testWidgets('DPadControl renders all four arrows', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: DPadControl(onPress: (_) {}, onRelease: () {}),
        ),
      ),
    );
    expect(find.byKey(const Key('dpad-up')), findsOneWidget);
    expect(find.byKey(const Key('dpad-down')), findsOneWidget);
    expect(find.byKey(const Key('dpad-left')), findsOneWidget);
    expect(find.byKey(const Key('dpad-right')), findsOneWidget);
  });
}
