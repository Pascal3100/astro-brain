import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../theme/theme_cubit.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

/// Barre d'état globale en haut de la Home :
/// - pastille + label `overall` (tap → écran System)
/// - bouton toggle jour/nuit (soleil/lune)
class StatusBar extends StatelessWidget {
  const StatusBar({super.key, required this.onOpenSystem});

  final VoidCallback onOpenSystem;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocBuilder<AppBloc, AppState>(
      builder: (ctx, state) {
        final overall = state.effectiveOverall;
        final mode = ctx.watch<ThemeCubit>().state;
        return HudPanel(
          padding: const EdgeInsets.symmetric(
            horizontal: DesignTokens.spaceLG,
            vertical: DesignTokens.spaceMD,
          ),
          child: Row(
            children: [
              InkWell(
                onTap: onOpenSystem,
                borderRadius: BorderRadius.circular(DesignTokens.radiusPill),
                child: Padding(
                  padding: const EdgeInsets.all(DesignTokens.spaceSM),
                  child: Row(
                    children: [
                      GlobalDot(
                        status: overall,
                        size: DesignTokens.statusDotSizeLg,
                      ),
                      const SizedBox(width: DesignTokens.spaceMD),
                      Text(overall.name.toUpperCase(), style: text.hudLabel),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              if (state.connection == ConnectionStatus.offline)
                IconButton(
                  tooltip: 'Reconnecter au Pi',
                  icon: PhosphorIcon(PhosphorIconsBold.arrowClockwise,
                      color: colors.accent),
                  onPressed: () =>
                      ctx.read<AppBloc>().add(const AppReconnectRequested()),
                ),
              IconButton(
                tooltip: mode == AstroThemeMode.day
                    ? 'Passer en mode nuit'
                    : 'Passer en mode jour',
                icon: PhosphorIcon(
                  mode == AstroThemeMode.day
                      ? PhosphorIconsBold.moon
                      : PhosphorIconsBold.sun,
                  color: colors.accent,
                ),
                onPressed: () => ctx.read<ThemeCubit>().toggle(),
              ),
            ],
          ),
        );
      },
    );
  }
}
