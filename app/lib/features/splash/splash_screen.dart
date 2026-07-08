import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../setup/network/network_screen.dart';
import 'splash_cubit.dart';
import 'splash_state.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.onReady});
  final VoidCallback onReady;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SplashCubit>().start();
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return Scaffold(
      body: BlocListener<SplashCubit, SplashState>(
        listener: (ctx, state) {
          if (state.phase == SplashPhase.success) widget.onReady();
        },
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [colors.bgGradientTop, colors.bgGradientBottom],
            ),
          ),
          child: SafeArea(
            child: BlocBuilder<SplashCubit, SplashState>(
              builder: (ctx, state) {
                final failed = state.phase == SplashPhase.failure;
                return Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      failed
                          ? PhosphorIconsBold.warning
                          : PhosphorIconsBold.planet,
                      size: DesignTokens.iconSizeXL * 2,
                      color: failed ? colors.dotError : colors.accent,
                    ),
                    const SizedBox(height: DesignTokens.spaceXL),
                    Text('ASTRO-BRAIN V 0.1', style: text.hudLabel),
                    const SizedBox(height: DesignTokens.space2XL),
                    _Step(
                      label: 'CONTACTING ASTRO-BRAIN.LOCAL',
                      state: stepStatusFor(state, SplashPhase.contacting),
                    ),
                    _Step(
                      label: 'LOADING STATE SNAPSHOT',
                      state: stepStatusFor(state, SplashPhase.loading),
                    ),
                    _Step(
                      label: 'OPENING EVENT STREAM',
                      state: stepStatusFor(state, SplashPhase.openingStream),
                    ),
                    if (failed) ...[
                      const SizedBox(height: DesignTokens.space2XL),
                      Text(
                        'ASTRO-BRAIN NOT REACHABLE',
                        style:
                            text.hudValue.copyWith(color: colors.dotError),
                      ),
                      const SizedBox(height: DesignTokens.spaceLG),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          FilledButton(
                            key: const Key('splash-retry'),
                            onPressed: () => ctx.read<SplashCubit>().start(),
                            child: const Text('RETRY'),
                          ),
                          const SizedBox(width: DesignTokens.spaceMD),
                          TextButton(
                            key: const Key('splash-continue-offline'),
                            onPressed: () =>
                                ctx.read<SplashCubit>().continueOffline(),
                            child: const Text('CONTINUE OFFLINE →'),
                          ),
                        ],
                      ),
                      const SizedBox(height: DesignTokens.spaceSM),
                      // L'hôte par défaut (mDNS) ou une IP obsolète est la cause
                      // n°1 d'un splash en échec : rendre la config réseau
                      // atteignable ici plutôt que via CONTINUE OFFLINE → Setup.
                      TextButton(
                        key: const Key('splash-configure-network'),
                        onPressed: () => Navigator.of(ctx).push(
                          MaterialPageRoute<void>(
                            builder: (_) => const NetworkScreen(),
                          ),
                        ),
                        child: const Text('CONFIGURER LE RÉSEAU'),
                      ),
                    ],
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

}

enum SplashStepState { pending, active, done, error }

/// Statut visuel d'une étape [p] du splash pour l'état [s]. Fonction pure
/// (extraite pour être testable directement, cf. bug d'affichage : en `failure`
/// toutes les étapes paraissaient « faites »).
SplashStepState stepStatusFor(SplashState s, SplashPhase p) {
  if (s.phase == SplashPhase.failure) {
    final failed = s.failedPhase ?? SplashPhase.contacting;
    if (p.index < failed.index) return SplashStepState.done; // franchie avant l'échec
    if (p == failed) return SplashStepState.error; // l'étape qui a échoué
    return SplashStepState.pending; // jamais atteinte
  }
  if (s.phase.index > p.index || s.phase == SplashPhase.success) {
    return SplashStepState.done;
  }
  if (s.phase == p) return SplashStepState.active;
  return SplashStepState.pending;
}

class _Step extends StatelessWidget {
  const _Step({required this.label, required this.state});
  final String label;
  final SplashStepState state;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final icon = switch (state) {
      SplashStepState.pending => PhosphorIconsRegular.circle,
      SplashStepState.active => PhosphorIconsBold.circleDashed,
      SplashStepState.done => PhosphorIconsBold.check,
      SplashStepState.error => PhosphorIconsBold.x,
    };
    final color = switch (state) {
      SplashStepState.pending => colors.textMuted,
      SplashStepState.active => colors.accent,
      SplashStepState.done => colors.accent,
      SplashStepState.error => colors.dotError,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceXS),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          PhosphorIcon(icon, color: color, size: DesignTokens.iconSizeSM),
          const SizedBox(width: DesignTokens.spaceSM),
          Text(label, style: text.hudCaption.copyWith(color: color)),
        ],
      ),
    );
  }
}
