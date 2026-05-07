import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/sensor_readings.dart';
import '../../../services/api_service.dart';
import '../../../services/pi_host.dart';
import '../../../services/tilt_stream_service.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import 'limits_bloc.dart';
import 'limits_event.dart';
import 'limits_state.dart';

/// Écran « Courses ALT » (item #4 du Setup) — capture ALT_min / ALT_max.
class LimitsAltScreen extends StatelessWidget {
  const LimitsAltScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<LimitsAltBloc>(
      create: (_) => LimitsAltBloc(api: context.read<ApiService>())
        ..add(const LimitsAltReloaded()),
      child: const _LimitsAltView(),
    );
  }
}

class _LimitsAltView extends StatefulWidget {
  const _LimitsAltView();

  @override
  State<_LimitsAltView> createState() => _LimitsAltViewState();
}

class _LimitsAltViewState extends State<_LimitsAltView> {
  late final TiltStreamService _tilt;
  StreamSubscription<TiltReading>? _tiltSub;

  /// Dernier `pitchDeg` reçu — utilisé pour les snapshots au tap des boutons
  /// de capture (le BLoC ne consomme pas le stream lui-même).
  double? _liveAltDeg;

  @override
  void initState() {
    super.initState();
    final host = context.read<PiHost>();
    _tilt = TiltStreamService(host: host, hz: 5)..start();
    _tiltSub = _tilt.stream.listen((r) => _liveAltDeg = r.pitchDeg);
  }

  @override
  void dispose() {
    _tiltSub?.cancel();
    _tilt.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocListener<LimitsAltBloc, LimitsAltState>(
      listenWhen: (prev, curr) =>
          prev.isSaved != curr.isSaved ||
          prev.errorMessage != curr.errorMessage,
      listener: (ctx, state) {
        if (state.isSaved) {
          ScaffoldMessenger.of(ctx).showSnackBar(
            const SnackBar(content: Text('Limites ALT enregistrées.')),
          );
          Navigator.of(ctx).pop(true);
        } else if (state.errorMessage != null) {
          ScaffoldMessenger.of(ctx).showSnackBar(
            SnackBar(content: Text(state.errorMessage!)),
          );
        }
      },
      child: Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [colors.bgGradientTop, colors.bgGradientBottom],
            ),
          ),
          child: SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.setup),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(DesignTokens.spaceLG),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'COURSES ALT',
                          style: text.hudLabel.copyWith(
                            color: colors.accent,
                            letterSpacing: 2.0,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          'Pointez le tube au plus bas accessible, capturez ; '
                          'pointez au plus haut, capturez ; enregistrez. '
                          'Écart minimum : 30°.',
                          style: text.hudCaption.copyWith(
                            color: colors.textMuted,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        _LiveAltReadout(stream: _tilt.stream),
                        const SizedBox(height: DesignTokens.spaceLG),
                        _CaptureButtons(getLiveAlt: () => _liveAltDeg),
                        const SizedBox(height: DesignTokens.spaceMD),
                        const _RangeWarning(),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _SaveButton(),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Affichage central de l'angle ALT live (gros chiffres).
class _LiveAltReadout extends StatelessWidget {
  const _LiveAltReadout({required this.stream});

  final Stream<TiltReading> stream;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return HudPanel(
      child: StreamBuilder<TiltReading>(
        stream: stream,
        builder: (ctx, snap) {
          final reading = snap.data;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'ALT COURANT',
                style: text.hudLabel.copyWith(color: colors.textMuted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: DesignTokens.spaceSM),
              Center(
                child: reading == null
                    ? SizedBox(
                        width: DesignTokens.iconSizeMD,
                        height: DesignTokens.iconSizeMD,
                        child: CircularProgressIndicator(
                          strokeWidth: DesignTokens.strokeRegular,
                          color: colors.accent,
                        ),
                      )
                    : Text(
                        '${reading.pitchDeg.toStringAsFixed(1)}°',
                        style: text.hudValue.copyWith(
                          color: colors.textPrimary,
                          fontSize: 48,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1.0,
                        ),
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _CaptureButtons extends StatelessWidget {
  const _CaptureButtons({required this.getLiveAlt});

  final double? Function() getLiveAlt;

  @override
  Widget build(BuildContext context) {
    final text = context.textStyles;
    return BlocBuilder<LimitsAltBloc, LimitsAltState>(
      builder: (ctx, state) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _CaptureButton(
              labelInitial: 'POINTER LE PLUS BAS',
              capturedDeg: state.lowerDeg,
              onTap: () {
                final deg = getLiveAlt();
                if (deg == null) return;
                ctx.read<LimitsAltBloc>().add(LimitsAltLowerCaptured(deg));
              },
              prefixWhenCaptured: 'ALT_min capturé',
              textStyles: text,
            ),
            const SizedBox(height: DesignTokens.spaceMD),
            _CaptureButton(
              labelInitial: 'POINTER LE PLUS HAUT',
              capturedDeg: state.upperDeg,
              onTap: () {
                final deg = getLiveAlt();
                if (deg == null) return;
                ctx.read<LimitsAltBloc>().add(LimitsAltUpperCaptured(deg));
              },
              prefixWhenCaptured: 'ALT_max capturé',
              textStyles: text,
            ),
          ],
        );
      },
    );
  }
}

class _CaptureButton extends StatelessWidget {
  const _CaptureButton({
    required this.labelInitial,
    required this.capturedDeg,
    required this.onTap,
    required this.prefixWhenCaptured,
    required this.textStyles,
  });

  final String labelInitial;
  final double? capturedDeg;
  final VoidCallback onTap;
  final String prefixWhenCaptured;
  final AppTextStyles textStyles;

  @override
  Widget build(BuildContext context) {
    final captured = capturedDeg != null;
    final label = captured
        ? '✓ $prefixWhenCaptured : ${capturedDeg!.toStringAsFixed(1)}°'
        : labelInitial;
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        // Re-capture autorisée : l'utilisateur peut overrider une valeur
        // déjà capturée tant qu'il n'a pas enregistré.
        onPressed: onTap,
        style: captured
            ? FilledButton.styleFrom(
                backgroundColor: Theme.of(context)
                    .colorScheme
                    .surfaceContainerHighest
                    .withValues(alpha: 0.4),
              )
            : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceSM),
          child: Text(label, style: textStyles.hudBadge),
        ),
      ),
    );
  }
}

class _RangeWarning extends StatelessWidget {
  const _RangeWarning();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<LimitsAltBloc, LimitsAltState>(
      buildWhen: (prev, curr) =>
          prev.hasRangeWarning != curr.hasRangeWarning,
      builder: (ctx, state) {
        if (!state.hasRangeWarning) return const SizedBox.shrink();
        final colors = context.colors;
        final text = context.textStyles;
        return Container(
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotWarn.withValues(alpha: 0.12),
            border: Border.all(
              color: colors.dotWarn.withValues(alpha: 0.6),
              width: DesignTokens.strokeThin,
            ),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.warning_amber_rounded,
                color: colors.dotWarn,
                size: DesignTokens.iconSizeMD,
              ),
              const SizedBox(width: DesignTokens.spaceSM),
              Expanded(
                child: Text(
                  'Plage trop faible. Vérifiez vos pointages '
                  '(écart minimum 30°).',
                  style: text.hudCaption.copyWith(color: colors.textPrimary),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SaveButton extends StatelessWidget {
  const _SaveButton();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<LimitsAltBloc, LimitsAltState>(
      builder: (ctx, state) {
        final enabled = state.canSave;
        return SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: enabled
                ? () => ctx
                    .read<LimitsAltBloc>()
                    .add(const LimitsAltSaveRequested())
                : null,
            child: Padding(
              padding:
                  const EdgeInsets.symmetric(vertical: DesignTokens.spaceMD),
              child: state.isSaving
                  ? SizedBox(
                      width: DesignTokens.iconSizeMD,
                      height: DesignTokens.iconSizeMD,
                      child: CircularProgressIndicator(
                        strokeWidth: DesignTokens.strokeRegular,
                        color: context.colors.accent,
                      ),
                    )
                  : Text(
                      'ENREGISTRER',
                      style: context.textStyles.hudBadge,
                    ),
            ),
          ),
        );
      },
    );
  }
}
