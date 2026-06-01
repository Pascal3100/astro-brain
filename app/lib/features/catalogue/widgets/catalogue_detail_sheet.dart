import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../catalogue_models.dart';
import '../constellations.dart';

/// Bottom sheet de détail d'un objet + bouton POINTER (grisé si non aligné).
class CatalogueDetailSheet extends StatelessWidget {
  const CatalogueDetailSheet({
    super.key,
    required this.object,
    required this.isAligned,
    required this.onGoto,
  });

  final CatalogObjectDto object;
  final bool isAligned;
  final VoidCallback onGoto;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    Widget cell(String k, String v) => Container(
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.bgGradientTop.withValues(alpha: 0.6),
            border: Border.all(color: colors.accent.withValues(alpha: 0.18)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(k, style: text.hudLabel.copyWith(color: colors.textMuted)),
              const SizedBox(height: DesignTokens.spaceXS),
              Text(v, style: text.hudValue.copyWith(color: colors.textPrimary)),
            ],
          ),
        );

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(DesignTokens.spaceLG),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
          Text(
            object.name,
            style:
                text.hudValue.copyWith(color: colors.textPrimary, fontSize: 22),
          ),
          const SizedBox(height: DesignTokens.spaceXS),
          Text(
            [
              if (object.designation != null) object.designation!,
              if (object.constellation != null)
                constellationFullName(object.constellation)!,
            ].join(' · '),
            style: text.hudCaption.copyWith(color: colors.textMuted),
          ),
          const SizedBox(height: DesignTokens.spaceLG),
          Row(
            children: [
              Expanded(
                child: cell(
                  'MAGNITUDE',
                  object.mag?.toStringAsFixed(2) ?? '—',
                ),
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: cell(
                  'ALTITUDE',
                  object.altitudeDeg != null
                      ? '${object.altitudeDeg!.round()}°'
                      : '—',
                ),
              ),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceMD),
          Row(
            children: [
              Expanded(
                child: cell(
                  'AZIMUT',
                  object.azimuthDeg != null
                      ? '${object.azimuthDeg!.round()}°'
                      : '—',
                ),
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: cell(
                  'AD / DÉC',
                  '${(object.raDeg / 15).toStringAsFixed(1)}h'
                  ' / ${object.decDeg.round()}°',
                ),
              ),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceLG),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: isAligned
                  ? () {
                      Navigator.of(context).pop();
                      onGoto();
                    }
                  : null,
              child: const Text('⌖ POINTER (GOTO)'),
            ),
          ),
          if (!isAligned) ...[
            const SizedBox(height: DesignTokens.spaceSM),
            Text(
              "Monture non alignée — alignez d'abord",
              style: text.hudCaption.copyWith(color: colors.dotWarn),
            ),
          ],
          ],
        ),
      ),
    );
  }
}
