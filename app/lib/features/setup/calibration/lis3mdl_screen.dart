import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/calibration.dart';
import '../../../models/sensor_readings.dart';
import '../../../services/api_service.dart';
import '../../../services/calibration_progress_stream.dart';
import '../../../services/compass_stream_service.dart';
import '../../../services/pi_host.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import 'calibration_bloc.dart';
import 'widgets/calibration_progress.dart';

const _sensorId = 'lis3mdl';

/// Écran de calibration « compass » (item #1 du Setup).
///
/// Spécificités :
/// - Après `done`, on n'auto-pop pas : on affiche un preview heading via
///   [CompassStreamService] à 5 Hz et un bouton FERMER.
class Lis3mdlScreen extends StatelessWidget {
  const Lis3mdlScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiService>();
    final host = context.read<PiHost>();
    return BlocProvider<CalibrationBloc>(
      create: (_) => CalibrationBloc(
        api: api,
        sensorId: _sensorId,
        finalizeGate: lis3mdlCanFinalize,
        progressStream: (sessionId) => CalibrationProgressStream(
          host: host,
          sensorId: _sensorId,
          sessionId: sessionId,
        ).open(),
      ),
      child: const _Lis3mdlView(),
    );
  }
}

class _Lis3mdlView extends StatefulWidget {
  const _Lis3mdlView();

  @override
  State<_Lis3mdlView> createState() => _Lis3mdlViewState();
}

class _Lis3mdlViewState extends State<_Lis3mdlView> {
  /// Service du preview heading post-finalize. Instancié au passage en
  /// `done`, fermé à `dispose()`.
  CompassStreamService? _compass;

  void _ensureCompassStarted() {
    if (_compass != null) return;
    final host = context.read<PiHost>();
    // setState() sinon le _HeadingPreview garde sa référence à `null`
    // et n'apprend jamais que le service vient de démarrer.
    setState(() {
      _compass = CompassStreamService(host: host, hz: 5)..start();
    });
  }

  @override
  void dispose() {
    _compass?.dispose();
    _compass = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocListener<CalibrationBloc, CalibrationBlocState>(
      listenWhen: (prev, curr) => prev.status != curr.status,
      listener: (ctx, state) {
        if (state.status == CalibrationState.done) {
          // On n'auto-pop pas : on ouvre le preview heading.
          // Le pop avec `true` se fait via le bouton FERMER.
          _ensureCompassStarted();
        } else if (state.status == CalibrationState.aborted) {
          Navigator.of(ctx).pop(false);
        } else if (state.status == CalibrationState.error) {
          ScaffoldMessenger.of(ctx).showSnackBar(
            SnackBar(content: Text(state.errorMessage ?? 'Erreur inconnue')),
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
                          'COMPASS',
                          style: text.hudLabel.copyWith(
                            color: colors.accent,
                            letterSpacing: 2.0,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          'Tournez le module dans toutes les directions '
                          'pour couvrir la sphère magnétique. Visez ≥ 80 % '
                          'de couverture avant de valider.',
                          style: text.hudCaption.copyWith(
                            color: colors.textMuted,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _ProgressPanel(),
                        const SizedBox(height: DesignTokens.spaceLG),
                        _ActionButtons(
                          onClose: () => Navigator.of(context).pop(true),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        _HeadingPreview(service: _compass),
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

class _ProgressPanel extends StatelessWidget {
  const _ProgressPanel();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CalibrationBloc, CalibrationBlocState>(
      buildWhen: (prev, curr) =>
          prev.progress != curr.progress || prev.status != curr.status,
      builder: (ctx, state) {
        if (state.status == CalibrationState.idle) {
          final text = context.textStyles;
          final colors = context.colors;
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceLG),
            child: Text(
              'Pressez DÉMARRER pour lancer la session.',
              style: text.hudCaption.copyWith(color: colors.textMuted),
              textAlign: TextAlign.center,
            ),
          );
        }
        if (state.status == CalibrationState.done) {
          return _DoneSummary(status: state.finalizedStatus);
        }
        return CalibrationProgressWidget(progress: state.progress);
      },
    );
  }
}

class _DoneSummary extends StatelessWidget {
  const _DoneSummary({required this.status});

  final CalibrationStatus? status;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final payload = status?.payload;
    final coverage = payload is Lis3mdlOffsets
        ? '${payload.coveragePct.toStringAsFixed(0)} %'
        : '—';
    final residual = payload is Lis3mdlOffsets
        ? payload.residual.toStringAsFixed(4)
        : '—';
    return HudPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                Icons.check_circle_outline,
                color: colors.dotOk,
                size: DesignTokens.iconSizeMD,
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Text(
                'CALIBRATION VALIDÉE',
                style: text.hudLabel.copyWith(color: colors.accent),
              ),
            ],
          ),
          const SizedBox(height: DesignTokens.spaceMD),
          _SummaryRow(label: 'COUVERTURE', value: coverage),
          const SizedBox(height: DesignTokens.spaceXS),
          _SummaryRow(label: 'RÉSIDU', value: residual),
        ],
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value});
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

class _ActionButtons extends StatelessWidget {
  const _ActionButtons({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CalibrationBloc, CalibrationBlocState>(
      builder: (ctx, state) {
        final isIdle =
            state.status == CalibrationState.idle ||
            state.status == CalibrationState.error;
        final isSampling = state.status == CalibrationState.sampling;
        final isComputing = state.status == CalibrationState.computing;
        final isDone = state.status == CalibrationState.done;

        return Wrap(
          spacing: DesignTokens.spaceSM,
          runSpacing: DesignTokens.spaceSM,
          children: [
            if (isIdle)
              FilledButton(
                onPressed: () =>
                    ctx.read<CalibrationBloc>().add(const CalibrationStarted()),
                child: Text('DÉMARRER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              FilledButton(
                onPressed: state.canFinalize && !isComputing
                    ? () => ctx.read<CalibrationBloc>().add(
                        const CalibrationFinalizeRequested(),
                      )
                    : null,
                child: Text('VALIDER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              OutlinedButton(
                onPressed: isComputing
                    ? null
                    : () => ctx.read<CalibrationBloc>().add(
                        const CalibrationAbortRequested(),
                      ),
                child: Text('ANNULER', style: context.textStyles.hudBadge),
              ),
            if (isDone)
              FilledButton(
                onPressed: onClose,
                child: Text('FERMER', style: context.textStyles.hudBadge),
              ),
          ],
        );
      },
    );
  }
}

/// Preview heading post-finalize. Affiché uniquement après `done`, quand
/// le service a été instancié par le State parent.
class _HeadingPreview extends StatelessWidget {
  const _HeadingPreview({required this.service});

  final CompassStreamService? service;

  @override
  Widget build(BuildContext context) {
    final svc = service;
    if (svc == null) return const SizedBox.shrink();
    final colors = context.colors;
    final text = context.textStyles;
    return HudPanel(
      child: StreamBuilder<CompassReading>(
        stream: svc.stream,
        builder: (ctx, snap) {
          final reading = snap.data;
          if (reading == null) {
            return Row(
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
                  'CONNEXION AU FLUX HEADING…',
                  style: text.hudCaption.copyWith(color: colors.textMuted),
                ),
              ],
            );
          }
          final qualifier = reading.tiltCompensated
              ? 'tilt-compensé'
              : 'naïve — niveau monture non calibré';
          return Row(
            children: [
              Icon(
                Icons.explore_outlined,
                color: colors.accent,
                size: DesignTokens.iconSizeMD,
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: Text(
                  'Cap actuel : ${reading.headingDeg.toStringAsFixed(1)}° '
                  '($qualifier)',
                  style: text.hudValue.copyWith(color: colors.textPrimary),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
