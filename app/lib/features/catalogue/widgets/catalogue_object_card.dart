import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../catalogue_models.dart';

/// Carte aérée d'un objet du catalogue (option B du design — lisibilité).
///
/// Affiche le nom principal, la désignation + constellation en sous-titre,
/// une pilule magnitude et une pilule altitude (surlignée quand visible).
class CatalogueObjectCard extends StatelessWidget {
  const CatalogueObjectCard({
    super.key,
    required this.object,
    required this.onTap,
  });

  final CatalogObjectDto object;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final subtitleParts = <String>[
      if (object.designation != null) object.designation!,
      if (object.constellation != null) object.constellation!,
    ];
    final subtitle = subtitleParts.join(' · ');

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
        child: Container(
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.bgGradientTop.withValues(alpha: 0.5),
            border: Border.all(
              color: colors.accent.withValues(alpha: 0.18),
            ),
            borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      object.name,
                      style: text.hudValue.copyWith(
                        color: colors.textPrimary,
                        fontSize: 16,
                      ),
                    ),
                    if (subtitle.isNotEmpty) ...[
                      const SizedBox(height: DesignTokens.spaceXS),
                      Text(
                        subtitle,
                        style: text.hudCaption.copyWith(
                          color: colors.textMuted,
                        ),
                      ),
                    ],
                    const SizedBox(height: DesignTokens.spaceSM),
                    Row(
                      children: [
                        if (object.mag != null)
                          _Pill(
                            label: 'mag ${object.mag!.toStringAsFixed(1)}',
                          ),
                        if (object.mag != null && object.altitudeDeg != null)
                          const SizedBox(width: DesignTokens.spaceSM),
                        if (object.altitudeDeg != null)
                          _Pill(
                            label: 'ALT ${object.altitudeDeg!.round()}°',
                            highlight: object.isVisible,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: DesignTokens.spaceSM),
              PhosphorIcon(
                PhosphorIconsBold.caretRight,
                color: colors.accent,
                size: DesignTokens.iconSizeSM,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, this.highlight = false});

  final String label;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final c = highlight ? colors.dotOk : colors.textMuted;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: DesignTokens.spaceSM,
        vertical: DesignTokens.spaceXXS,
      ),
      decoration: BoxDecoration(
        border: Border.all(color: c.withValues(alpha: 0.5)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
      ),
      child: Text(label, style: text.hudBadge.copyWith(color: c)),
    );
  }
}
