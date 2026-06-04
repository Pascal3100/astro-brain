import 'package:flutter/material.dart';

import '../../../features/catalogue/constellations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/dpad_control.dart';
import '../../../widgets/hud_panel.dart';
import '../../../widgets/rate_control.dart';
import '../alignment_models.dart';
import '../alignment_repository.dart';
import '../widgets/constellation_chart.dart';

/// Écran par étoile du wizard d'alignement (mockup D2).
///
/// Reçoit les données cible et les callbacks métier depuis le caller (wizard).
/// Le [repo] est utilisé exclusivement pour le chargement à la demande de la
/// figure de constellation — aucune autre logique métier dans cet écran.
class PerStarScreen extends StatefulWidget {
  const PerStarScreen({
    super.key,
    required this.repo,
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

  final AlignmentRepository repo;
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

  @override
  State<PerStarScreen> createState() => _PerStarScreenState();
}

class _PerStarScreenState extends State<PerStarScreen> {
  bool _loadingConstellation = false;

  double get _dAz => widget.targetAz - widget.currentAz;
  double get _dAlt => widget.targetAlt - widget.currentAlt;

  /// Abréviation IAU extraite du champ Bayer (ex. "α UMa" → "UMa").
  String get _constellationAbbr {
    final parts = widget.target.bayer.trim().split(' ');
    return parts.length >= 2 ? parts.last : '';
  }

  Future<void> _showConstellationSheet() async {
    final abbr = _constellationAbbr;
    if (abbr.isEmpty) return;

    setState(() => _loadingConstellation = true);
    try {
      final figure = await widget.repo.fetchConstellation(
        abbr,
        raDeg: widget.target.raDeg,
        decDeg: widget.target.decDeg,
      );
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        isScrollControlled: true,
        builder: (ctx) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              DesignTokens.spaceLG,
              DesignTokens.spaceXS,
              DesignTokens.spaceLG,
              DesignTokens.spaceLG,
            ),
            child: ConstellationChart(figure: figure),
          ),
        ),
      );
    } on Exception {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Schéma indisponible pour cette constellation'),
        ),
      );
    } finally {
      if (mounted) setState(() => _loadingConstellation = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final abbr = _constellationAbbr;
    final constellationName = constellationFullName(abbr);

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
                  '// ÉTOILE ${widget.stepIndex} / ${widget.totalSteps}',
                  style: text.hudCaption.copyWith(
                    fontSize: 10,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  widget.target.name.toUpperCase(),
                  style: text.hudValue.copyWith(
                    fontSize: 26,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1.3,
                    color: colors.textPrimary,
                  ),
                ),
                Text(
                  '${widget.target.bayer} · mag ${widget.target.mag} · '
                  'AZ ${widget.targetAz.round()}° / ALT ${widget.targetAlt.round()}°',
                  style: TextStyle(fontSize: 11, color: colors.textMuted),
                ),
                if (constellationName != null) ...[
                  const SizedBox(height: DesignTokens.spaceXS),
                  Text(
                    constellationName.toUpperCase(),
                    style: text.hudCaption.copyWith(
                      fontSize: 10,
                      letterSpacing: 0.8,
                      color: colors.accent,
                    ),
                  ),
                ],
                if (abbr.isNotEmpty) ...[
                  const SizedBox(height: DesignTokens.spaceSM),
                  OutlinedButton.icon(
                    onPressed:
                        _loadingConstellation ? null : _showConstellationSheet,
                    icon: _loadingConstellation
                        ? SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: colors.accent,
                            ),
                          )
                        : Icon(Icons.star_outline, size: 16, color: colors.accent),
                    label: Text(
                      'Voir dans la constellation',
                      style: TextStyle(fontSize: 12, color: colors.accent),
                    ),
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: colors.accent.withValues(alpha: 0.5)),
                      padding: const EdgeInsets.symmetric(
                        horizontal: DesignTokens.spaceMD,
                        vertical: DesignTokens.spaceXS,
                      ),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                ],
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
                    onPress: widget.onPress,
                    // Le contrat externe accepte un VoidCallback pour rester
                    // simple côté caller ; le DPadControl émet la direction
                    // relâchée — qu'on ignore ici.
                    onRelease: (_) => widget.onRelease(),
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceMD),
                RateControl(value: widget.rate, onChanged: widget.onRateChanged),
                const SizedBox(height: DesignTokens.spaceLG),
                _CenteredButton(onTap: widget.onCentered),
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
    final text = context.textStyles;
    return Row(
      children: [
        SizedBox(
          width: 36,
          child: Text(
            label,
            style: text.hudCaption.copyWith(
              fontSize: 9,
              color: colors.textMuted,
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
            style: text.hudValue.copyWith(
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
          'CENTRÉ ✓',
          textAlign: TextAlign.center,
          style: text.hudCaption.copyWith(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: colors.bgGradientTop,
          ),
        ),
      ),
    );
  }
}
