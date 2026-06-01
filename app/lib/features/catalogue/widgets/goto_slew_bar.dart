import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';

/// Barre de slew GoTo : nom de cible, progression indéterminée, bouton STOP.
/// (Progression indéterminée : INDI ne donne pas de % fiable.)
class GotoSlewBar extends StatelessWidget {
  const GotoSlewBar({
    super.key,
    required this.targetName,
    required this.onStop,
  });

  final String targetName;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.all(DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientBottom,
        border: Border(
          top: BorderSide(color: colors.accent.withValues(alpha: 0.4)),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'GOTO → $targetName',
                style: text.hudLabel.copyWith(color: colors.textPrimary),
              ),
              Text(
                'EN COURS',
                style: text.hudBadge.copyWith(color: colors.dotWarn),
              ),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceSM),
          LinearProgressIndicator(color: colors.accent),
          const SizedBox(height: DesignTokens.spaceSM),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: onStop,
              child: const Text('■ STOP'),
            ),
          ),
        ],
      ),
    );
  }
}
