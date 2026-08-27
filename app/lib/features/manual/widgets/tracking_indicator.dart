import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/subsystem_states.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/hud_panel.dart';

/// Indicateur de suivi sidéral — lecture seule.
///
/// Il n'y a plus de commande côté app : le suivi s'arme tout seul à la
/// première étoile validée de l'alignement, comme le fait la raquette
/// Celestron (sniff du bus AUX, ADR 2026-08-27). Reste à le *voir*, pour
/// distinguer « monture figée » de « monture qui suit » sans sortir du HUD.
class TrackingIndicator extends StatelessWidget {
  const TrackingIndicator({super.key});

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
        // Sans lien ou sans monture prête, l'état publié n'est pas
        // signifiant : on l'affiche comme inconnu plutôt que comme « off ».
        final known =
            state.connection == ConnectionStatus.connected && mountReady;
        final tracking =
            state.system?.tracking.state == TrackingState.sidereal;
        final active = known && tracking;

        final (label, hint) = switch ((known, tracking)) {
          (false, _) => ('TRACKING —', 'monture non disponible'),
          (true, true) => ('TRACKING SIDEREAL', 'la monture compense la rotation du ciel'),
          (true, false) => ('TRACKING OFF', "s'arme à la 1ʳᵉ étoile validée"),
        };

        return Opacity(
          opacity: known ? 1 : 0.35,
          child: HudPanel(
            child: Row(
              children: [
                PhosphorIcon(
                  PhosphorIconsBold.crosshairSimple,
                  color: active ? colors.accent : colors.textMuted,
                ),
                const SizedBox(width: DesignTokens.spaceMD),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: text.hudValue.copyWith(
                          color: active ? colors.accent : colors.textMuted,
                        ),
                      ),
                      const SizedBox(height: DesignTokens.spaceXS),
                      Text(
                        hint,
                        style: text.hudCaption.copyWith(
                          color: colors.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
