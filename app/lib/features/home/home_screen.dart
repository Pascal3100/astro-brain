import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/design_tokens.dart';
import 'widgets/dpad_control.dart';
import 'widgets/rate_control.dart';
import 'widgets/status_bar.dart';
import 'widgets/tracking_toggle.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.onOpenSystem});
  final VoidCallback onOpenSystem;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              children: [
                StatusBar(onOpenSystem: onOpenSystem),
                const SizedBox(height: DesignTokens.space2XL),
                const Expanded(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: DPadControl(),
                    ),
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXL),
                const RateControl(),
                const SizedBox(height: DesignTokens.spaceXL),
                const TrackingToggle(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
