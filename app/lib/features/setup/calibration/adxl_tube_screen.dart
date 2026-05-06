import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/sensor_readings.dart';
import '../../../services/api_service.dart';
import '../../../services/calibration_progress_stream.dart';
import '../../../services/pi_host.dart';
import '../../../services/tilt_stream_service.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import 'adxl_tube_bloc.dart';
import 'adxl_tube_event.dart';
import 'adxl_tube_state.dart';
import 'widgets/calibration_progress.dart';

const _sensorId = 'adxl345_tube';

/// Écran de calibration « zéro ALT » (item #3 du Setup).
///
/// Spécificité vs. ADXL mount : un preview live de l'angle ALT lu sur le
/// stream tilt, affiché au-dessus du bouton VALIDER pendant la session.
/// Le backend persiste `zero_alt_deg = 0` par convention — c'est l'instant
/// du clic VALIDER qui définit la position « tube horizontal ».
class AdxlTubeScreen extends StatelessWidget {
  const AdxlTubeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiService>();
    final host = context.read<PiHost>();
    return BlocProvider<AdxlTubeBloc>(
      create: (_) => AdxlTubeBloc(
        api: api,
        progressStream: (sessionId) => CalibrationProgressStream(
          host: host,
          sensorId: _sensorId,
          sessionId: sessionId,
        ).open(),
      ),
      child: const _AdxlTubeView(),
    );
  }
}

class _AdxlTubeView extends StatefulWidget {
  const _AdxlTubeView();

  @override
  State<_AdxlTubeView> createState() => _AdxlTubeViewState();
}

class _AdxlTubeViewState extends State<_AdxlTubeView> {
  /// Tilt live preview, démarré au passage en `sampling`. Possédé par
  /// l'écran et fermé à `dispose()`.
  TiltStreamService? _tilt;

  void _ensureTiltStarted() {
    if (_tilt != null) return;
    final host = context.read<PiHost>();
    // setState() sinon le _TiltPreview garde sa référence à `null` et
    // n'apprend jamais que le service vient de démarrer.
    setState(() {
      _tilt = TiltStreamService(host: host, hz: 5)..start();
    });
  }

  @override
  void dispose() {
    _tilt?.dispose();
    _tilt = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocListener<AdxlTubeBloc, AdxlTubeState>(
      listenWhen: (prev, curr) => prev.status != curr.status,
      listener: (ctx, state) {
        if (state.status == AdxlTubeStatus.sampling) {
          _ensureTiltStarted();
        } else if (state.status == AdxlTubeStatus.done) {
          Navigator.of(ctx).pop(true);
        } else if (state.status == AdxlTubeStatus.aborted) {
          Navigator.of(ctx).pop(false);
        } else if (state.status == AdxlTubeStatus.error) {
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
                          'ZÉRO ALT',
                          style: text.hudLabel.copyWith(
                            color: colors.accent,
                            letterSpacing: 2.0,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          'Placez le tube horizontal, immobile.\n'
                          'Quand vous appuierez sur VALIDER, la position '
                          'courante deviendra le zéro ALT.',
                          style: text.hudCaption.copyWith(
                            color: colors.textMuted,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _ProgressPanel(),
                        const SizedBox(height: DesignTokens.spaceMD),
                        _TiltPreview(service: _tilt),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _ActionButtons(),
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
    return BlocBuilder<AdxlTubeBloc, AdxlTubeState>(
      buildWhen: (prev, curr) =>
          prev.progress != curr.progress || prev.status != curr.status,
      builder: (ctx, state) {
        if (state.status == AdxlTubeStatus.idle) {
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
        return CalibrationProgressWidget(progress: state.progress);
      },
    );
  }
}

/// Affiche l'angle ALT live (pitch tilt-corrigé) pendant la session.
/// Invisible avant le démarrage et après l'arrêt du service.
class _TiltPreview extends StatelessWidget {
  const _TiltPreview({required this.service});

  final TiltStreamService? service;

  @override
  Widget build(BuildContext context) {
    final svc = service;
    if (svc == null) return const SizedBox.shrink();
    final colors = context.colors;
    final text = context.textStyles;
    return HudPanel(
      child: StreamBuilder<TiltReading>(
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
                  'CONNEXION AU FLUX TILT…',
                  style: text.hudCaption.copyWith(color: colors.textMuted),
                ),
              ],
            );
          }
          return Row(
            children: [
              Icon(
                Icons.straighten,
                color: colors.accent,
                size: DesignTokens.iconSizeMD,
              ),
              const SizedBox(width: DesignTokens.spaceMD),
              Expanded(
                child: Text(
                  'Position courante : ${reading.pitchDeg.toStringAsFixed(1)}°'
                  ' — quand vous validerez, cette position deviendra le zéro.',
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

class _ActionButtons extends StatelessWidget {
  const _ActionButtons();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AdxlTubeBloc, AdxlTubeState>(
      builder: (ctx, state) {
        final isIdle =
            state.status == AdxlTubeStatus.idle ||
            state.status == AdxlTubeStatus.error;
        final isSampling = state.status == AdxlTubeStatus.sampling;
        final isComputing = state.status == AdxlTubeStatus.computing;

        return Wrap(
          spacing: DesignTokens.spaceSM,
          runSpacing: DesignTokens.spaceSM,
          children: [
            if (isIdle)
              FilledButton(
                onPressed: () =>
                    ctx.read<AdxlTubeBloc>().add(const AdxlTubeStarted()),
                child: Text('DÉMARRER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              FilledButton(
                onPressed: state.canFinalize && !isComputing
                    ? () => ctx.read<AdxlTubeBloc>().add(
                        const AdxlTubeFinalizeRequested(),
                      )
                    : null,
                child: Text('VALIDER', style: context.textStyles.hudBadge),
              ),
            if (isSampling || isComputing)
              OutlinedButton(
                onPressed: isComputing
                    ? null
                    : () => ctx.read<AdxlTubeBloc>().add(
                        const AdxlTubeAbortRequested(),
                      ),
                child: Text('ANNULER', style: context.textStyles.hudBadge),
              ),
          ],
        );
      },
    );
  }
}
