import 'package:flutter/material.dart';

import '../../../../models/calibration.dart' as model;
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';
import '../../../../theme/design_tokens.dart';
import '../../../../widgets/hud_panel.dart';

/// Affiche un état de progression de calibration.
///
/// `progress == null` rend un état d'attente. Sinon : spinner + nombre
/// d'échantillons + sigma + (optionnel) couverture sphérique + hint.
class CalibrationProgressWidget extends StatelessWidget {
  const CalibrationProgressWidget({
    super.key,
    required this.progress,
    this.sensorIdLabel,
  });

  final model.CalibrationProgress? progress;
  final String? sensorIdLabel;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final p = progress;

    if (p == null) {
      return HudPanel(
        child: Row(
          children: [
            SizedBox(
              width: DesignTokens.iconSizeMD,
              height: DesignTokens.iconSizeMD,
              child: CircularProgressIndicator(
                strokeWidth: DesignTokens.strokeRegular,
                color: colors.accent,
              ),
            ),
            const SizedBox(width: DesignTokens.spaceMD),
            Text(
              'EN ATTENTE…',
              style: text.hudCaption.copyWith(color: colors.textMuted),
            ),
          ],
        ),
      );
    }

    return HudPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              SizedBox(
                width: DesignTokens.iconSizeMD,
                height: DesignTokens.iconSizeMD,
                child: CircularProgressIndicator(
                  strokeWidth: DesignTokens.strokeRegular,
                  color: colors.accent,
                ),
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: Text(
                  sensorIdLabel ?? 'ÉCHANTILLONNAGE EN COURS',
                  style: text.hudLabel.copyWith(color: colors.accent),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceMD),
          _Metric(label: 'ÉCHANTILLONS', value: '${p.samplesN}'),
          const SizedBox(height: DesignTokens.spaceXS),
          _Metric(label: 'SIGMA', value: p.sigma.toStringAsFixed(4)),
          if (p.coveragePct > 0) ...[
            const SizedBox(height: DesignTokens.spaceXS),
            _Metric(
              label: 'COUVERTURE',
              value: '${p.coveragePct.toStringAsFixed(0)} %',
            ),
            const SizedBox(height: DesignTokens.spaceXS),
            ClipRRect(
              borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
              child: LinearProgressIndicator(
                value: (p.coveragePct / 100.0).clamp(0.0, 1.0),
                minHeight: DesignTokens.strokeRegular * 2,
                backgroundColor: colors.grid,
                valueColor: AlwaysStoppedAnimation<Color>(colors.accent),
              ),
            ),
          ],
          if (p.hint != null && p.hint!.isNotEmpty) ...[
            const SizedBox(height: DesignTokens.spaceMD),
            Text(
              p.hint!,
              style: text.hudCaption.copyWith(color: colors.textMuted),
            ),
          ],
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: text.hudCaption.copyWith(color: colors.textMuted),
          ),
        ),
        Text(value, style: text.hudValue.copyWith(color: colors.textPrimary)),
      ],
    );
  }
}
