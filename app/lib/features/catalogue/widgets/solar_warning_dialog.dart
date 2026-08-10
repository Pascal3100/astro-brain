import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';

/// Dialogue d'avertissement avant un GoTo sur le Soleil. Retourne `true`
/// si l'utilisateur confirme (→ renvoi du GoTo avec `confirm_solar: true`),
/// `false` sinon. Politique décidée côté backend (server-driven) ; ce
/// dialogue est purement l'acquittement humain du danger.
Future<bool> showSolarWarningDialog(BuildContext context) async {
  final colors = context.colors;
  final text = context.textStyles;
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: colors.bgGradientBottom,
      title: Text('⚠ Pointage vers le Soleil',
          style: text.hudValue.copyWith(color: colors.dotWarn)),
      content: Text(
        'Pointer le télescope vers le Soleil sans filtre solaire adapté '
        'peut détruire l\'instrument et causer des lésions oculaires '
        'irréversibles. Ne confirme que si tu sais ce que tu fais.',
        style: text.hudCaption.copyWith(color: colors.textPrimary),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: const Text('ANNULER'),
        ),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: colors.dotWarn),
          onPressed: () => Navigator.of(ctx).pop(true),
          child: const Text('POINTER QUAND MÊME'),
        ),
      ],
    ),
  );
  return confirmed ?? false;
}
