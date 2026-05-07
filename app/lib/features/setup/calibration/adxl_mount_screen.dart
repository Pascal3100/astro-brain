import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../services/api_service.dart';
import '../../../services/calibration_progress_stream.dart';
import '../../../services/pi_host.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import 'calibration_bloc.dart';
import 'widgets/calibration_progress.dart';

const _sensorId = 'adxl345_mount';

/// Écran de calibration « niveau monture » (item #1 du Setup).
class AdxlMountScreen extends StatelessWidget {
  const AdxlMountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiService>();
    final host = context.read<PiHost>();
    return BlocProvider<CalibrationBloc>(
      create: (_) => CalibrationBloc(
        api: api,
        sensorId: _sensorId,
        finalizeGate: adxlCanFinalize,
        progressStream: (sessionId) => CalibrationProgressStream(
          host: host,
          sensorId: _sensorId,
          sessionId: sessionId,
        ).open(),
      ),
      child: const _AdxlMountView(),
    );
  }
}

class _AdxlMountView extends StatelessWidget {
  const _AdxlMountView();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocListener<CalibrationBloc, CalibrationBlocState>(
      listenWhen: (prev, curr) => prev.status != curr.status,
      listener: (ctx, state) {
        if (state.status == CalibrationState.done) {
          Navigator.of(ctx).pop(true);
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
                          'NIVEAU MONTURE',
                          style: text.hudLabel.copyWith(
                            color: colors.accent,
                            letterSpacing: 2.0,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          'Posez la monture niveau, immobile.\n'
                          'L\'échantillonnage démarre dès que vous appuyez sur '
                          'DÉMARRER.',
                          style: text.hudCaption.copyWith(
                            color: colors.textMuted,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _ProgressPanel(),
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
        return CalibrationProgressWidget(progress: state.progress);
      },
    );
  }
}

class _ActionButtons extends StatelessWidget {
  const _ActionButtons();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CalibrationBloc, CalibrationBlocState>(
      builder: (ctx, state) {
        final isIdle =
            state.status == CalibrationState.idle ||
            state.status == CalibrationState.error;
        final isSampling = state.status == CalibrationState.sampling;
        final isComputing = state.status == CalibrationState.computing;

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
          ],
        );
      },
    );
  }
}
