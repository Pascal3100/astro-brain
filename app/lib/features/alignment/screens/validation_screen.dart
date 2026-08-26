import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import '../alignment_models.dart';

/// Écran présentationnel de validation du modèle d'alignement (Option C).
///
/// Affiche le RMS global, les 3 résiduels sous forme de barres, l'éventuel
/// outlier mis en avant (accent + glow), un encart diagnostic, puis les
/// actions REFAIRE / ACCEPTER. Les interactions remontent via callbacks pour
/// rester découplé du BLoC : le caller orchestre la logique métier.
class ValidationScreen extends StatelessWidget {
  const ValidationScreen({
    super.key,
    required this.model,
    required this.candidates,
    required this.onAccept,
    required this.onRestartStar,
  });

  final AlignmentModelDto model;
  final List<StarDto> candidates;
  final VoidCallback onAccept;
  final ValueChanged<int> onRestartStar;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final outlierId = model.outlierId;
    final outlierIdx = outlierId == null
        ? -1
        : candidates.indexWhere((c) => c.id == outlierId);
    final outlierName =
        outlierIdx >= 0 ? candidates[outlierIdx].name.toUpperCase() : '';
    // Échelle des barres : on prend le pic comme 100 %, garde-fou à 1 arc-min
    // pour éviter la division par zéro et un plafond raisonnable.
    final maxResid = model.residuals.values
        .fold<double>(0, (a, b) => b > a ? b : a)
        .clamp(1, 1000);

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
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.alignment),
                const SizedBox(height: DesignTokens.spaceLG),
                Text(
                  '// VALIDATION',
                  style: text.hudCaption.copyWith(
                    fontSize: 10,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  'RÉSULTAT',
                  style: text.hudValue.copyWith(
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      'RMS GLOBAL',
                      style: text.hudCaption.copyWith(
                        fontSize: 9,
                        color: colors.textMuted,
                      ),
                    ),
                    const SizedBox(width: DesignTokens.spaceSM),
                    Text(
                      model.rmsArcmin.toStringAsFixed(1),
                      style: text.hudValue.copyWith(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: colors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'arc-min',
                      style: text.hudCaption.copyWith(
                        fontSize: 11,
                        color: colors.textMuted,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: DesignTokens.spaceMD),
                HudPanel(
                  child: Column(
                    children: candidates.map((c) {
                      final r = model.residuals[c.id] ?? 0.0;
                      final isOutlier = c.id == outlierId;
                      return _ResidualRow(
                        name: c.name.toUpperCase(),
                        residual: r,
                        widthFactor: (r / maxResid).clamp(0.05, 1.0),
                        isOutlier: isOutlier,
                      );
                    }).toList(),
                  ),
                ),
                if (outlierName.isNotEmpty) ...[
                  const SizedBox(height: DesignTokens.spaceMD),
                  _DiagnosticBlock(outlierName: outlierName),
                ],
                const SizedBox(height: DesignTokens.spaceLG),
                Row(
                  children: [
                    if (outlierIdx >= 0) ...[
                      Expanded(
                        child: OutlinedButton(
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(
                              vertical: DesignTokens.spaceLG,
                            ),
                            side: BorderSide(
                              color: colors.accent.withValues(alpha: 0.5),
                              width: 1.5,
                            ),
                          ),
                          onPressed: () => onRestartStar(outlierIdx),
                          child: Text(
                            'REFAIRE $outlierName',
                            style: text.hudCaption.copyWith(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 1.2,
                              color: colors.accent,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: DesignTokens.spaceMD),
                    ],
                    Expanded(
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: colors.accent,
                          padding: const EdgeInsets.symmetric(
                            vertical: DesignTokens.spaceLG,
                          ),
                        ),
                        onPressed: onAccept,
                        child: Text(
                          'ACCEPTER',
                          style: text.hudCaption.copyWith(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.5,
                            color: colors.bgGradientTop,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ResidualRow extends StatelessWidget {
  const _ResidualRow({
    required this.name,
    required this.residual,
    required this.widthFactor,
    required this.isOutlier,
  });

  final String name;
  final double residual;
  final double widthFactor;
  final bool isOutlier;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final color = isOutlier ? colors.accent : colors.textPrimary;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(
            width: 90,
            child: Text(
              name,
              style: text.hudValue.copyWith(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
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
              child: Align(
                alignment: Alignment.centerLeft,
                child: FractionallySizedBox(
                  widthFactor: widthFactor,
                  child: Container(
                    decoration: BoxDecoration(
                      color: isOutlier
                          ? colors.accent
                          : colors.textPrimary.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(3),
                      boxShadow: isOutlier
                          ? [
                              BoxShadow(
                                color: colors.accent.withValues(alpha: 0.6),
                                blurRadius: 8,
                              ),
                            ]
                          : null,
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: DesignTokens.spaceSM),
          SizedBox(
            width: 56,
            child: Text(
              "${residual.toStringAsFixed(1)}'",
              textAlign: TextAlign.right,
              style: text.hudValue.copyWith(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticBlock extends StatelessWidget {
  const _DiagnosticBlock({required this.outlierName});

  final String outlierName;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.all(DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.accent.withValues(alpha: 0.06),
        border: Border(left: BorderSide(color: colors.accent, width: 2)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: outlierName,
                  style: text.hudValue.copyWith(
                    fontWeight: FontWeight.w600,
                    color: colors.accent,
                  ),
                ),
                TextSpan(
                  text: ' a un résiduel anormal. Causes possibles :',
                  style: TextStyle(
                    fontSize: 11,
                    color: colors.textPrimary.withValues(alpha: 0.75),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          ...const [
            '• Centrage imprécis dans l\'oculaire',
            '• Mauvaise étoile pointée',
            '• Jeu mécanique de la monture (backlash)',
          ].map(
            (s) => Padding(
              padding: const EdgeInsets.only(left: 4, top: 2),
              child: Text(
                s,
                style: TextStyle(
                  fontSize: 11,
                  color: colors.textPrimary.withValues(alpha: 0.75),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
