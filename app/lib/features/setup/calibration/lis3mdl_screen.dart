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
import 'lis3mdl_bloc.dart';
import 'lis3mdl_event.dart';
import 'lis3mdl_state.dart';
import 'widgets/calibration_progress.dart';

const _sensorId = 'lis3mdl';

/// Écran de calibration « compass » (item #2 du Setup).
///
/// Spécificités vs. ADXL mount :
/// - Soft warning au démarrage si `adxl345_mount` n'est pas calibré (le
///   heading sera moins précis, mais on peut quand même calibrer).
/// - Après `done`, on n'auto-pop pas : on affiche un preview heading via
///   [CompassStreamService] à 5 Hz et un bouton FERMER.
class Lis3mdlScreen extends StatelessWidget {
  const Lis3mdlScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiService>();
    final host = context.read<PiHost>();
    return BlocProvider<Lis3mdlBloc>(
      create: (_) => Lis3mdlBloc(
        api: api,
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
  /// `null` tant que la requête n'a pas répondu, `true` si l'ADXL mount
  /// est calibré, `false` sinon (status payload null OU erreur réseau —
  /// le warning est best-effort).
  bool? _mountCalibrated;

  /// Service du preview heading post-finalize. Instancié au passage en
  /// `done`, fermé à `dispose()`.
  CompassStreamService? _compass;

  @override
  void initState() {
    super.initState();
    _checkMountCalibration();
  }

  Future<void> _checkMountCalibration() async {
    try {
      final status = await context.read<ApiService>().getCalibrationStatus(
        'adxl345_mount',
      );
      if (!mounted) return;
      setState(() => _mountCalibrated = status.payload != null);
    } catch (_) {
      // Best-effort : si le Pi est injoignable, on n'affiche pas le
      // warning plutôt que de planter l'écran.
      if (!mounted) return;
      setState(() => _mountCalibrated = true);
    }
  }

  void _ensureCompassStarted() {
    if (_compass != null) return;
    final host = context.read<PiHost>();
    _compass = CompassStreamService(host: host, hz: 5)..start();
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

    return BlocListener<Lis3mdlBloc, Lis3mdlState>(
      listenWhen: (prev, curr) => prev.status != curr.status,
      listener: (ctx, state) {
        if (state.status == Lis3mdlStatus.done) {
          // On n'auto-pop pas : on ouvre le preview heading.
          // Le pop avec `true` se fait via le bouton FERMER.
          _ensureCompassStarted();
        } else if (state.status == Lis3mdlStatus.aborted) {
          Navigator.of(ctx).pop(false);
        } else if (state.status == Lis3mdlStatus.error) {
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
                        const SizedBox(height: DesignTokens.spaceMD),
                        if (_mountCalibrated == false)
                          const _MountNotCalibratedWarning(),
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

/// Bandeau soft warning — affiché uniquement quand l'ADXL mount n'est pas
/// calibré. Pas de blocage : la calibration LIS3MDL fonctionne sans, mais
/// le preview heading sera "naïve" plutôt que "tilt-compensé".
class _MountNotCalibratedWarning extends StatelessWidget {
  const _MountNotCalibratedWarning();

  @override
  Widget build(BuildContext context) {
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
              'Niveau monture non calibré — le heading sera moins précis. '
              'Recommandé : faire d\'abord l\'item #1.',
              style: text.hudCaption.copyWith(color: colors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressPanel extends StatelessWidget {
  const _ProgressPanel();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<Lis3mdlBloc, Lis3mdlState>(
      buildWhen: (prev, curr) =>
          prev.progress != curr.progress || prev.status != curr.status,
      builder: (ctx, state) {
        if (state.status == Lis3mdlStatus.idle) {
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
        if (state.status == Lis3mdlStatus.done) {
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
    return BlocBuilder<Lis3mdlBloc, Lis3mdlState>(
      builder: (ctx, state) {
        final isIdle =
            state.status == Lis3mdlStatus.idle ||
            state.status == Lis3mdlStatus.error;
        final isSampling = state.status == Lis3mdlStatus.sampling;
        final isComputing = state.status == Lis3mdlStatus.computing;
        final isDone = state.status == Lis3mdlStatus.done;

        return Wrap(
          spacing: DesignTokens.spaceSM,
          runSpacing: DesignTokens.spaceSM,
          children: [
            if (isIdle)
              FilledButton(
                onPressed: () =>
                    ctx.read<Lis3mdlBloc>().add(const Lis3mdlStarted()),
                child: Text('DÉMARRER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              FilledButton(
                onPressed: state.canFinalize && !isComputing
                    ? () => ctx.read<Lis3mdlBloc>().add(
                        const Lis3mdlFinalizeRequested(),
                      )
                    : null,
                child: Text('VALIDER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              OutlinedButton(
                onPressed: isComputing
                    ? null
                    : () => ctx.read<Lis3mdlBloc>().add(
                        const Lis3mdlAbortRequested(),
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
