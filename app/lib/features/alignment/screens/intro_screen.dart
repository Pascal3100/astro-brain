import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';

/// Écran d'accueil du wizard d'alignement 3 étoiles.
///
/// Présente un titre HUD + bouton DÉMARRER. La liste des candidates et
/// l'option de swap seront ajoutés en T20 (cold-start restore prompt).
class IntroScreen extends StatelessWidget {
  const IntroScreen({super.key, required this.onStart});

  final VoidCallback onStart;

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
                const SizedBox(height: DesignTokens.spaceXL),
                Text(
                  '// MISE EN STATION',
                  style: text.hudCaption.copyWith(
                    fontSize: 10,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  'ALIGNEMENT',
                  style: text.hudValue.copyWith(
                    fontSize: 32,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 2.0,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                Text(
                  'Le wizard va sélectionner 3 étoiles brillantes et te '
                  'guider pour les centrer une à une dans l\'oculaire.',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: colors.textPrimary.withValues(alpha: 0.85),
                  ),
                ),
                const Spacer(),
                _StartButton(onTap: onStart),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StartButton extends StatelessWidget {
  const _StartButton({required this.onTap});

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
          'DÉMARRER',
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
