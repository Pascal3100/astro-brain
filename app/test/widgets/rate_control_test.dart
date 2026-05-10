import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:astro_brain/theme/design_tokens.dart';
import 'package:astro_brain/widgets/rate_control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _testTheme() => ThemeData(
      extensions: [
        AppColors.day,
        AppTextStyles.build(color: DesignTokens.dayText),
      ],
    );

void main() {
  testWidgets('RateControl plus button increments value', (tester) async {
    int last = 4;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: StatefulBuilder(builder: (ctx, set) {
            return RateControl(
              value: last,
              onChanged: (v) => set(() => last = v),
            );
          }),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('rate-plus')));
    await tester.pump();
    expect(last, 5);
  });

  testWidgets('RateControl minus button decrements value', (tester) async {
    int last = 4;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: StatefulBuilder(builder: (ctx, set) {
            return RateControl(
              value: last,
              onChanged: (v) => set(() => last = v),
            );
          }),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('rate-minus')));
    await tester.pump();
    expect(last, 3);
  });

  testWidgets('RateControl displays N segments active', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: RateControl(value: 3, onChanged: (_) {}),
        ),
      ),
    );
    expect(find.byKey(const Key('rate-seg-on')), findsNWidgets(3));
    expect(find.byKey(const Key('rate-seg-off')), findsNWidgets(6));
  });

  testWidgets('RateControl plus disabled at max', (tester) async {
    var changes = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: RateControl(value: 9, onChanged: (_) => changes++),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('rate-plus')));
    await tester.pump();
    expect(changes, 0);
  });

  testWidgets('RateControl minus disabled at min', (tester) async {
    var changes = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: _testTheme(),
        home: Scaffold(
          body: RateControl(value: 1, onChanged: (_) => changes++),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('rate-minus')));
    await tester.pump();
    expect(changes, 0);
  });
}
