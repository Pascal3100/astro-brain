import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../setup/reference/reference_models.dart';
import '../../setup/reference/reference_repository.dart';

/// Bandeau affiché quand l'almanach de référence LOCAL est absent
/// (`ready == false`) : premier lancement, ou offline sans cache. Invite à
/// synchroniser dans Réglages → Almanach. Masqué tant que le futur de statut
/// n'a pas de donnée, ou si l'almanach local est prêt (`ready == true`).
class ReferenceBanner extends StatelessWidget {
  const ReferenceBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return FutureBuilder<ReferenceStatusDto>(
      future: context.read<ReferenceRepository>().getStatus(),
      builder: (ctx, snap) {
        // Pas de donnée exploitable (chargement ou erreur réseau) → rien.
        if (!snap.hasData || snap.data!.ready) return const SizedBox.shrink();
        return Container(
          margin: const EdgeInsets.all(DesignTokens.spaceMD),
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotWarn.withValues(alpha: 0.1),
            border: Border.all(color: colors.dotWarn.withValues(alpha: 0.4)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Text(
            'Almanach absent — synchronise dans Réglages.',
            style: text.hudCaption.copyWith(color: colors.dotWarn),
          ),
        );
      },
    );
  }
}
