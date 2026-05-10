import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../theme/design_tokens.dart';

/// Widget présentationnel de contrôle de vitesse (rate).
///
/// Aucune dépendance BLoC — la valeur est passée via [value] et les
/// changements remontent via [onChanged]. Le caller détermine comment
/// mapper la valeur vers des commandes métier.
///
/// Clés testables : `'rate-minus'`, `'rate-plus'`,
/// `'rate-seg-on'` (segments actifs), `'rate-seg-off'` (segments inactifs).
class RateControl extends StatelessWidget {
  const RateControl({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 1,
    this.max = 9,
  });

  /// Valeur courante (entre [min] et [max] inclus).
  final int value;

  /// Appelé avec la nouvelle valeur quand l'utilisateur appuie sur + ou −.
  final ValueChanged<int> onChanged;

  /// Valeur minimale autorisée (défaut 1).
  final int min;

  /// Valeur maximale autorisée (défaut 9).
  final int max;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final canDecrement = value > min;
    final canIncrement = value < max;

    return Row(
      children: [
        IconButton(
          key: const Key('rate-minus'),
          onPressed: canDecrement ? () => onChanged(value - 1) : null,
          icon: PhosphorIcon(
            PhosphorIconsBold.minus,
            color: colors.accent.withValues(alpha: canDecrement ? 1.0 : 0.3),
          ),
        ),
        Expanded(
          child: Row(
            children: List.generate(max, (i) {
              final active = i < value;
              return Expanded(
                child: KeyedSubtree(
                  key: Key(active ? 'rate-seg-on' : 'rate-seg-off'),
                  child: Container(
                    margin: const EdgeInsets.symmetric(
                        horizontal: DesignTokens.spaceXXS),
                    height: DesignTokens.spaceLG,
                    decoration: BoxDecoration(
                      color: active
                          ? colors.accent
                          : colors.accent.withValues(alpha: 0.15),
                      borderRadius:
                          BorderRadius.circular(DesignTokens.radiusSM),
                    ),
                  ),
                ),
              );
            }),
          ),
        ),
        IconButton(
          key: const Key('rate-plus'),
          onPressed: canIncrement ? () => onChanged(value + 1) : null,
          icon: PhosphorIcon(
            PhosphorIconsBold.plus,
            color: colors.accent.withValues(alpha: canIncrement ? 1.0 : 0.3),
          ),
        ),
        SizedBox(
          width: 28,
          child: Text(
            '$value',
            textAlign: TextAlign.center,
            style: text.hudValue,
          ),
        ),
      ],
    );
  }
}
