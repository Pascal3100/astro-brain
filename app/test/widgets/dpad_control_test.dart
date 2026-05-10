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
            onRelease: (_) => releases++,
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
          body: DPadControl(onPress: (_) {}, onRelease: (_) {}),
        ),
      ),
    );
    expect(find.byKey(const Key('dpad-up')), findsOneWidget);
    expect(find.byKey(const Key('dpad-down')), findsOneWidget);
    expect(find.byKey(const Key('dpad-left')), findsOneWidget);
    expect(find.byKey(const Key('dpad-right')), findsOneWidget);
  });

  testWidgets('DPadControl emits release with same direction as press',
      (tester) async {
    DPadDirection? lastRelease;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: DPadControl(
            onPress: (_) {},
            onRelease: (d) => lastRelease = d,
          ),
        ),
      ),
    );
    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('dpad-left'))),
    );
    await gesture.up();
    await tester.pump();
    expect(lastRelease, DPadDirection.left);
  });

  testWidgets('DPadControl emits each of the four directions on its arrow',
      (tester) async {
    final pressed = <DPadDirection>[];
    // Constrain to 300×300 so all three grid rows fit within the 800×600
    // default test surface (dpad-down row would otherwise be clipped at y≈670).
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: SizedBox(
            width: 300,
            height: 300,
            child: DPadControl(
              onPress: pressed.add,
              onRelease: (_) {},
            ),
          ),
        ),
      ),
    );
    for (final key in ['dpad-up', 'dpad-down', 'dpad-left', 'dpad-right']) {
      final g =
          await tester.startGesture(tester.getCenter(find.byKey(Key(key))));
      await g.up();
      await tester.pump();
    }
    expect(pressed, [
      DPadDirection.up,
      DPadDirection.down,
      DPadDirection.left,
      DPadDirection.right,
    ]);
  });
}
