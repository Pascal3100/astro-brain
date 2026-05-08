import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/subsystem_states.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/hud_panel.dart';
import '../manual_bloc.dart';

class TrackingToggle extends StatelessWidget {
  const TrackingToggle({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) =>
          a.connection != b.connection ||
          a.system?.tracking.state != b.system?.tracking.state ||
          a.system?.mount.state != b.system?.mount.state,
      builder: (ctx, state) {
        final mountReady = state.system?.mount.state == MountState.ready ||
            state.system?.mount.state == MountState.moving;
        final disabled =
            state.connection != ConnectionStatus.connected || !mountReady;
        final enabled = state.system?.tracking.state == TrackingState.sidereal;
        return Opacity(
          opacity: disabled ? 0.35 : 1,
          child: IgnorePointer(
            ignoring: disabled,
            child: HudPanel(
              child: Row(
                children: [
                  PhosphorIcon(PhosphorIconsBold.crosshairSimple,
                      color: enabled ? colors.accent : colors.textMuted),
                  const SizedBox(width: DesignTokens.spaceMD),
                  Expanded(
                    child: Text(
                      enabled ? 'TRACKING SIDEREAL' : 'TRACKING OFF',
                      style: text.hudValue.copyWith(
                        color: enabled ? colors.accent : colors.textMuted,
                      ),
                    ),
                  ),
                  Switch(
                    value: enabled,
                    onChanged: (v) =>
                        ctx.read<ManualBloc>().add(ManualTrackingToggled(v)),
                    activeThumbColor: colors.accent,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
