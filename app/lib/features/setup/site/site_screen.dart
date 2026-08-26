import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/overall_status.dart';
import '../../../services/api_service.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';
import 'site_bloc.dart';
import 'site_event.dart';
import 'site_repository.dart';
import 'site_state.dart';

/// Formate une latitude/longitude en degrés décimaux signés.
String formatCoords(double lat, double lon) =>
    '${lat.toStringAsFixed(5)}°, ${lon.toStringAsFixed(5)}°';

class SiteScreen extends StatelessWidget {
  const SiteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<SiteBloc>(
      create: (_) => SiteBloc(
        repo: SiteRepository(api: context.read<ApiService>()),
      )..add(const SiteLoaded()),
      child: const SiteView(),
    );
  }
}

/// Vue pure — le bloc est fourni par [SiteScreen] (ou par un mock en test).
class SiteView extends StatelessWidget {
  const SiteView({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;

    return Scaffold(
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
                        "SITE D'OBSERVATION",
                        style: context.textStyles.hudLabel.copyWith(
                          color: colors.accent,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: DesignTokens.spaceLG),
                      const _SitePanel(),
                      const SizedBox(height: DesignTokens.spaceMD),
                      const _StatusRow(),
                      const SizedBox(height: DesignTokens.spaceLG),
                      const _ActionButton(),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SitePanel extends StatelessWidget {
  const _SitePanel();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocBuilder<SiteBloc, SiteState>(
      builder: (ctx, state) {
        final site = state.site;

        if (site == null) {
          return HudPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'AUCUN SITE',
                  style: text.hudLabel.copyWith(color: colors.textMuted),
                ),
                const SizedBox(height: DesignTokens.spaceSM),
                Text(
                  "Le Pi n'a plus de GPS : la position vient du téléphone. "
                  "L'alignement la demandera s'il en a besoin.",
                  style: text.hudCaption.copyWith(color: colors.textMuted),
                ),
              ],
            ),
          );
        }

        return HudPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _Field(label: 'LATITUDE', value: '${site.lat.toStringAsFixed(5)}°'),
              const SizedBox(height: DesignTokens.spaceMD),
              _Field(label: 'LONGITUDE', value: '${site.lon.toStringAsFixed(5)}°'),
              const SizedBox(height: DesignTokens.spaceMD),
              _Field(label: 'RÉGLÉ LE', value: _formatSetAt(site.setAt)),
            ],
          ),
        );
      },
    );
  }
}

String _formatSetAt(DateTime setAt) {
  final local = setAt.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} '
      '${two(local.hour)}:${two(local.minute)}';
}

class _Field extends StatelessWidget {
  const _Field({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: text.hudCaption.copyWith(color: colors.textMuted)),
        const SizedBox(height: DesignTokens.spaceSM),
        Text(value, style: text.hudValue.copyWith(color: colors.textPrimary)),
      ],
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow();

  @override
  Widget build(BuildContext context) {
    final text = context.textStyles;
    final colors = context.colors;

    return BlocBuilder<SiteBloc, SiteState>(
      builder: (ctx, state) {
        final (dotStatus, label) = switch (state.status) {
          SiteStatus.loading => (OverallStatus.blue, 'LECTURE…'),
          SiteStatus.saving => (OverallStatus.blue, 'ACQUISITION GPS…'),
          SiteStatus.error => (
              OverallStatus.red,
              'ERREUR: ${state.error ?? ''}',
            ),
          SiteStatus.ready => state.site == null
              ? (OverallStatus.gray, 'NON DÉFINI')
              : (OverallStatus.green, 'SITE DÉFINI'),
        };

        return Row(
          children: [
            GlobalDot(status: dotStatus),
            const SizedBox(width: DesignTokens.spaceSM),
            Expanded(
              child: Text(
                label,
                style: text.hudCaption.copyWith(color: colors.textMuted),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<SiteBloc, SiteState>(
      builder: (ctx, state) {
        final busy = state.status == SiteStatus.saving ||
            state.status == SiteStatus.loading;

        return FilledButton(
          onPressed: busy
              ? null
              : () => ctx.read<SiteBloc>().add(const SiteFromPhoneRequested()),
          child: Text(
            'UTILISER LA POSITION DU TÉLÉPHONE',
            style: context.textStyles.hudBadge,
          ),
        );
      },
    );
  }
}
