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
                      state: _stepStatus(state, SplashPhase.contacting),
                    ),
                    _Step(
                      label: 'LOADING STATE SNAPSHOT',
                      state: _stepStatus(state, SplashPhase.loading),
                    ),
                    _Step(
                      label: 'OPENING EVENT STREAM',
                      state: _stepStatus(state, SplashPhase.openingStream),
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
                            onPressed: () => ctx.read<SplashCubit>().start(),
                            child: const Text('RETRY'),
                          ),
                          const SizedBox(width: DesignTokens.spaceMD),
                          TextButton(
                            onPressed: () =>
                                ctx.read<SplashCubit>().continueOffline(),
                            child: const Text('CONTINUE OFFLINE →'),
                          ),
                        ],
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

  _StepState _stepStatus(SplashState s, SplashPhase p) {
    if (s.phase == SplashPhase.failure) {
      return s.phase.index > p.index ? _StepState.done : _StepState.error;
    }
    if (s.phase.index > p.index || s.phase == SplashPhase.success) {
      return _StepState.done;
    }
    if (s.phase == p) return _StepState.active;
    return _StepState.pending;
  }
}

enum _StepState { pending, active, done, error }

class _Step extends StatelessWidget {
  const _Step({required this.label, required this.state});
  final String label;
  final _StepState state;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final icon = switch (state) {
      _StepState.pending => PhosphorIconsRegular.circle,
      _StepState.active => PhosphorIconsBold.circleDashed,
      _StepState.done => PhosphorIconsBold.check,
      _StepState.error => PhosphorIconsBold.x,
    };
    final color = switch (state) {
      _StepState.pending => colors.textMuted,
      _StepState.active => colors.accent,
      _StepState.done => colors.accent,
      _StepState.error => colors.dotError,
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
