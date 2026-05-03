import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/overall_status.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

/// Carte de la liste Setup : index + icône + label + sous-label + dot d'état.
class SetupCard extends StatelessWidget {
  const SetupCard({
    super.key,
    required this.index,
    required this.icon,
    required this.label,
    required this.sublabel,
    required this.dotStatus,
    this.onTap,
  });

  final int index;
  final IconData icon;
  final String label;
  final String sublabel;
  final OverallStatus dotStatus;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final disabled = onTap == null;
    final fg = disabled ? colors.textMuted : colors.accent;

    return HudPanel(
      padding: EdgeInsets.zero,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
        child: Padding(
          padding: const EdgeInsets.all(DesignTokens.spaceLG),
          child: Row(
            children: [
              Text(
                index.toString().padLeft(2, '0'),
                style: text.hudLabel.copyWith(color: fg),
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              PhosphorIcon(icon, color: fg, size: DesignTokens.iconSizeMD),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      label,
                      style: text.hudLabel.copyWith(color: fg),
                    ),
                    Text(
                      sublabel,
                      style: text.hudCaption.copyWith(color: colors.textMuted),
                    ),
                  ],
                ),
              ),
              GlobalDot(
                status: dotStatus,
                size: DesignTokens.statusDotSize,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
