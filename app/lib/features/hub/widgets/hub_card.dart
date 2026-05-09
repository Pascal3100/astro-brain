import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';

/// Carte du Hub : hero icon + libellé + hint + chevron, pleine largeur.
/// Variant `primary` pour la première carte (gradient + glow accent).
class HubCard extends StatelessWidget {
  const HubCard({
    super.key,
    required this.heroIcon,
    required this.label,
    required this.hint,
    required this.onTap,
    this.primary = false,
  });

  final List<List<dynamic>> heroIcon;
  final String label;
  final String hint;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final bgGradient = primary
        ? LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              colors.accent.withValues(alpha: 0.12),
              colors.accent.withValues(alpha: 0.04),
            ],
          )
        : null;
    final borderColor = primary
        ? colors.accent.withValues(alpha: 0.4)
        : colors.accent.withValues(alpha: 0.18);
    final iconBg = primary
        ? colors.accent.withValues(alpha: 0.2)
        : colors.accent.withValues(alpha: 0.1);
    final iconShadow = primary
        ? [
            BoxShadow(
              color: colors.accent.withValues(alpha: 0.3),
              blurRadius: 16,
            ),
          ]
        : <BoxShadow>[];

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusXL),
        child: Container(
          decoration: BoxDecoration(
            gradient: bgGradient,
            color: bgGradient == null
                ? colors.accent.withValues(alpha: 0.04)
                : null,
            border: Border.all(color: borderColor),
            borderRadius: BorderRadius.circular(DesignTokens.radiusXL),
          ),
          padding: const EdgeInsets.all(DesignTokens.spaceLG),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
                  boxShadow: iconShadow,
                ),
                child: Center(
                  child: HugeIcon(
                    icon: heroIcon,
                    color: colors.accent,
                    size: 28,
                  ),
                ),
              ),
              const SizedBox(width: DesignTokens.spaceLG),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: text.hudLabel),
                    const SizedBox(height: 2),
                    Text(
                      hint,
                      style: text.hudCaption.copyWith(
                        color: colors.textMuted,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              PhosphorIcon(
                PhosphorIconsBold.caretRight,
                color: colors.accent.withValues(alpha: 0.4),
                size: DesignTokens.iconSizeMD,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
