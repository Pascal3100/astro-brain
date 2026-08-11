import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
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
                return Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      PhosphorIconsBold.planet,
                      size: DesignTokens.iconSizeXL * 2,
                      color: colors.accent,
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

enum SplashStepState { pending, active, done }

/// Statut visuel d'une étape [p] du splash pour l'état [s]. Fonction pure
/// (extraite pour être testable directement).
SplashStepState stepStatusFor(SplashState s, SplashPhase p) {
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
    };
    final color = switch (state) {
      SplashStepState.pending => colors.textMuted,
      SplashStepState.active => colors.accent,
      SplashStepState.done => colors.accent,
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
