import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/dpad_control.dart';
import '../../../widgets/hud_panel.dart';
import '../../../widgets/rate_control.dart';
import '../alignment_models.dart';

/// Écran présentationnel par étoile du wizard d'alignement (mockup D2).
///
/// Aucune dépendance BLoC : interactions remontées via callbacks. Le caller
/// compose la logique d'état et les commandes métier autour de ce widget.
class PerStarScreen extends StatelessWidget {
  const PerStarScreen({
    super.key,
    required this.stepIndex,
    required this.totalSteps,
    required this.target,
    required this.targetAz,
    required this.targetAlt,
    required this.currentAz,
    required this.currentAlt,
    required this.rate,
    required this.onPress,
    required this.onRelease,
    required this.onRateChanged,
    required this.onCentered,
  });

  final int stepIndex;
  final int totalSteps;
  final StarDto target;
  final double targetAz;
  final double targetAlt;
  final double currentAz;
  final double currentAlt;
  final int rate;
  final ValueChanged<DPadDirection> onPress;
  final VoidCallback onRelease;
  final ValueChanged<int> onRateChanged;
  final VoidCallback onCentered;

  double get _dAz => targetAz - currentAz;
  double get _dAlt => targetAlt - currentAlt;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
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
                const SizedBox(height: DesignTokens.spaceLG),
                Text(
                  '// ÉTOILE $stepIndex / $totalSteps',
                  style: TextStyle(
                    fontFamily: 'JetBrainsMono',
                    fontSize: 10,
                    letterSpacing: 1.5,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  target.name.toUpperCase(),
                  style: TextStyle(
                    fontFamily: 'JetBrainsMono',
                    fontSize: 26,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1.3,
                    color: colors.textPrimary,
                  ),
                ),
                Text(
                  '${target.bayer} · mag ${target.mag} · '
                  'AZ ${targetAz.round()}° / ALT ${targetAlt.round()}°',
                  style: TextStyle(fontSize: 11, color: colors.textMuted),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                HudPanel(
                  child: Column(
                    children: [
                      _AxisRow(label: 'AZ', delta: _dAz),
                      const Divider(height: DesignTokens.spaceMD),
                      _AxisRow(label: 'ALT', delta: _dAlt),
                    ],
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                AspectRatio(
                  aspectRatio: 1,
                  child: DPadControl(
                    onPress: onPress,
                    // Le contrat externe accepte un VoidCallback pour rester
                    // simple côté caller ; le DPadControl émet la direction
                    // relâchée — qu'on ignore ici.
                    onRelease: (_) => onRelease(),
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceMD),
                RateControl(value: rate, onChanged: onRateChanged),
                const SizedBox(height: DesignTokens.spaceLG),
                _CenteredButton(onTap: onCentered),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AxisRow extends StatelessWidget {
  const _AxisRow({required this.label, required this.delta});

  final String label;
  final double delta;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      children: [
        SizedBox(
          width: 36,
          child: Text(
            label,
            style: TextStyle(
              fontFamily: 'JetBrainsMono',
              fontSize: 9,
              color: colors.textMuted,
              letterSpacing: 1.5,
            ),
          ),
        ),
        Expanded(
          child: Container(
            height: 6,
            decoration: BoxDecoration(
              color: colors.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
        ),
        const SizedBox(width: DesignTokens.spaceSM),
        SizedBox(
          width: 56,
          child: Text(
            '${delta >= 0 ? '+' : ''}${delta.toStringAsFixed(1)}°',
            textAlign: TextAlign.right,
            style: TextStyle(
              fontFamily: 'JetBrainsMono',
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: colors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}

class _CenteredButton extends StatelessWidget {
  const _CenteredButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(DesignTokens.spaceLG),
        decoration: BoxDecoration(
          color: colors.accent,
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Text(
          'CENTRÉ ✓',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'JetBrainsMono',
            fontSize: 12,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
            color: colors.bgGradientTop,
          ),
        ),
      ),
    );
  }
}
