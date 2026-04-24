import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/overall_status.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

class SubsystemCard extends StatelessWidget {
  const SubsystemCard({
    super.key,
    required this.label,
    required this.icon,
    required this.stateLabel,
    required this.detailsText,
    required this.since,
    required this.dotStatus,
    this.message,
  });

  final String label;
  final IconData icon;
  final String stateLabel;
  final String detailsText;
  final DateTime since;
  final OverallStatus dotStatus;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final agoSeconds = DateTime.now().difference(since).inSeconds;
    return HudPanel(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PhosphorIcon(icon,
              color: colors.accent, size: DesignTokens.iconSizeLG),
          const SizedBox(width: DesignTokens.spaceLG),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(label, style: text.hudLabel),
                    const Spacer(),
                    GlobalDot(status: dotStatus),
                  ],
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(stateLabel, style: text.hudValue),
                if (detailsText.isNotEmpty) ...[
                  const SizedBox(height: DesignTokens.spaceXS),
                  Text(detailsText, style: text.hudCaption),
                ],
                const SizedBox(height: DesignTokens.spaceXS),
                Text('depuis ${_formatAgo(agoSeconds)}',
                    style: text.hudCaption
                        .copyWith(color: colors.textMuted)),
                if (message != null) ...[
                  const SizedBox(height: DesignTokens.spaceSM),
                  Text(message!,
                      style:
                          text.hudCaption.copyWith(color: colors.dotError)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatAgo(int seconds) {
    if (seconds < 60) return '${seconds}s';
    if (seconds < 3600) return '${seconds ~/ 60}min';
    return '${seconds ~/ 3600}h';
  }
}
