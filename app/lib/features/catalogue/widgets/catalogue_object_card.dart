import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../catalogue_models.dart';
import '../constellations.dart';

/// Carte aérée d'un objet du catalogue (design B — lisibilité priorisée).
///
/// Grand nom + badge magnitude en tête, sous-titre désignation · constellation
/// (nom complet), puis pilules ALT/AZ (ALT surlignée quand l'objet est visible).
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
      if (object.constellation != null)
        constellationFullName(object.constellation)!,
    ];
    final subtitle = subtitleParts.join(' · ');

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
        child: Container(
          padding: const EdgeInsets.all(DesignTokens.spaceLG),
          decoration: BoxDecoration(
            color: colors.bgGradientTop.withValues(alpha: 0.55),
            border: Border.all(
              color: colors.accent.withValues(alpha: 0.22),
            ),
            borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          object.name,
                          style: text.hudValue.copyWith(
                            color: colors.textPrimary,
                            fontSize: 20,
                            height: 1.1,
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
                      ],
                    ),
                  ),
                  if (object.mag != null) ...[
                    const SizedBox(width: DesignTokens.spaceMD),
                    _MagBadge(mag: object.mag!),
                  ],
                ],
              ),
              if (object.altitudeDeg != null) ...[
                const SizedBox(height: DesignTokens.spaceMD),
                Row(
                  children: [
                    _Pill(
                      label: '▲ ALT ${object.altitudeDeg!.round()}°',
                      highlight: object.isVisible,
                    ),
                    if (object.azimuthDeg != null) ...[
                      const SizedBox(width: DesignTokens.spaceSM),
                      _Pill(label: 'AZ ${object.azimuthDeg!.round()}°'),
                    ],
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MagBadge extends StatelessWidget {
  const _MagBadge({required this.mag});

  final double mag;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: DesignTokens.spaceSM,
        vertical: DesignTokens.spaceXXS,
      ),
      decoration: BoxDecoration(
        color: colors.accent.withValues(alpha: 0.12),
        border: Border.all(color: colors.accent.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
      ),
      child: Text(
        'mag ${mag.toStringAsFixed(1)}',
        style: text.hudBadge.copyWith(color: colors.textPrimary),
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
