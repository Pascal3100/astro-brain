import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../features/setup/setup_screen.dart';
import '../features/system/system_screen.dart';
import '../state/app_bloc/app_bloc.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import '../theme/design_tokens.dart';
import '../theme/theme_cubit.dart';
import 'global_dot.dart';
import 'hud_panel.dart';

enum AstroScreen { hub, manual, system, setup, about }

/// AppBar HUD partagée : pastille overall, icône setup, reconnect conditionnel, toggle thème.
class AstroAppBar extends StatelessWidget {
  const AstroAppBar({super.key, required this.current});

  final AstroScreen current;

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
              if (Navigator.of(context).canPop())
                IconButton(
                  tooltip: 'Retour',
                  icon: PhosphorIcon(
                    PhosphorIconsBold.caretLeft,
                    color: colors.accent,
                  ),
                  onPressed: () => Navigator.of(context).maybePop(),
                ),
              InkWell(
                onTap: current == AstroScreen.system
                    ? null
                    : () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const SystemScreen(),
                          ),
                        ),
                borderRadius:
                    BorderRadius.circular(DesignTokens.radiusPill),
                child: Padding(
                  padding: const EdgeInsets.all(DesignTokens.spaceSM),
                  child: Row(
                    children: [
                      GlobalDot(
                        status: overall,
                        size: DesignTokens.statusDotSizeLg,
                      ),
                      const SizedBox(width: DesignTokens.spaceMD),
                      Text(overall.displayLabel, style: text.hudLabel),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              if (state.connection == ConnectionStatus.offline)
                IconButton(
                  tooltip: 'Reconnecter au Pi',
                  icon: PhosphorIcon(
                    PhosphorIconsBold.arrowClockwise,
                    color: colors.accent,
                  ),
                  onPressed: () =>
                      ctx.read<AppBloc>().add(const AppReconnectRequested()),
                ),
              IconButton(
                tooltip: 'Paramètres',
                icon: PhosphorIcon(
                  PhosphorIconsBold.gearSix,
                  color: current == AstroScreen.setup
                      ? colors.accent.withValues(alpha: 0.4)
                      : colors.accent,
                ),
                onPressed: current == AstroScreen.setup
                    ? null
                    : () => Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => const SetupScreen(),
                          ),
                        ),
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
