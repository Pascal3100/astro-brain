import 'package:flutter/material.dart';

import '../models/overall_status.dart';
import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

/// Pastille colorée + halo glow. En mode `OverallStatus.blue` (transition),
/// elle clignote à 1 Hz (fade-in/out). En offline, rouge saturé fixe.
class GlobalDot extends StatefulWidget {
  const GlobalDot({
    super.key,
    required this.status,
    this.size = DesignTokens.statusDotSize,
  });

  final OverallStatus status;
  final double size;

  @override
  State<GlobalDot> createState() => _GlobalDotState();
}

class _GlobalDotState extends State<GlobalDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  Color _color(AppColors colors) => switch (widget.status) {
        OverallStatus.green => colors.dotOk,
        OverallStatus.blue => colors.dotTransition,
        OverallStatus.orange => colors.dotWarn,
        OverallStatus.red => colors.dotError,
        OverallStatus.offline => colors.dotError,
      };

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final color = _color(colors);
    final pulsing = widget.status == OverallStatus.blue;

    Widget dot(double opacity) => Container(
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            color: color.withValues(alpha: opacity),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: opacity * 0.8),
                blurRadius: widget.size,
                spreadRadius: 0,
              ),
            ],
          ),
        );

    if (!pulsing) return dot(1.0);
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, _) => dot(0.45 + 0.55 * _pulse.value),
    );
  }
}
