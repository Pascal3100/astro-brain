import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';

/// Écran terminal du wizard d'alignement : monture alignée, retour Hub.
class DoneScreen extends StatelessWidget {
  const DoneScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.alignment),
                const Spacer(),
                Text(
                  '// STATUT',
                  textAlign: TextAlign.center,
                  style: text.hudCaption.copyWith(
                    fontSize: 10,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  'MONTURE ALIGNÉE ✓',
                  textAlign: TextAlign.center,
                  style: text.hudValue.copyWith(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.5,
                    color: colors.accent,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                Text(
                  'Le télescope est prêt. Tu peux maintenant lancer un GoTo.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: colors.textPrimary.withValues(alpha: 0.85),
                  ),
                ),
                const Spacer(),
                _HubButton(
                  onTap: () => Navigator.of(context)
                      .popUntil((r) => r.isFirst),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HubButton extends StatelessWidget {
  const _HubButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(DesignTokens.spaceLG),
        decoration: BoxDecoration(
          color: colors.accent,
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Text(
          'RETOUR HUB',
          textAlign: TextAlign.center,
          style: text.hudCaption.copyWith(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
            color: colors.bgGradientTop,
          ),
        ),
      ),
    );
  }
}
