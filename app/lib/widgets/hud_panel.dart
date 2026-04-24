import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

/// Panneau HUD : fond légèrement tinté d'accent, bordure fine colorée.
/// Base visuelle des cards, du D-Pad, de la status bar.
class HudPanel extends StatelessWidget {
  const HudPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(DesignTokens.spaceLG),
    this.radius = DesignTokens.radiusLG,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Color.lerp(colors.bgGradientTop, colors.accent, 0.04),
        border: Border.all(
          color: colors.accent.withValues(alpha: 0.2),
          width: DesignTokens.strokeThin,
        ),
        borderRadius: BorderRadius.circular(radius),
      ),
      child: child,
    );
  }
}
