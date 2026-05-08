import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../services/api_service.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../version.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/hud_panel.dart';
import 'about_bloc.dart';
import 'about_event.dart';
import 'about_state.dart';

/// Écran « À propos » — informations système read-only.
class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<AboutBloc>(
      create: (_) => AboutBloc(api: context.read<ApiService>())
        ..add(const AboutLoaded()),
      child: const _AboutView(),
    );
  }
}

class _AboutView extends StatelessWidget {
  const _AboutView();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

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
              const AstroAppBar(current: AstroScreen.about),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(DesignTokens.spaceLG),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'À PROPOS',
                        style: text.hudLabel.copyWith(
                          color: colors.accent,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: DesignTokens.spaceLG),
                      const _ErrorBanner(),
                      const _InfoPanel(),
                      const SizedBox(height: DesignTokens.spaceLG),
                      const _RefreshButton(),
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

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AboutBloc, AboutState>(
      buildWhen: (prev, curr) => prev.errorMessage != curr.errorMessage,
      builder: (ctx, state) {
        if (state.errorMessage == null) return const SizedBox.shrink();
        final colors = context.colors;
        final text = context.textStyles;
        return Padding(
          padding: const EdgeInsets.only(bottom: DesignTokens.spaceMD),
          child: Container(
            padding: const EdgeInsets.all(DesignTokens.spaceMD),
            decoration: BoxDecoration(
              color: colors.dotError.withValues(alpha: 0.12),
              border: Border.all(
                color: colors.dotError.withValues(alpha: 0.6),
                width: DesignTokens.strokeThin,
              ),
              borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.error_outline_rounded,
                  color: colors.dotError,
                  size: DesignTokens.iconSizeMD,
                ),
                const SizedBox(width: DesignTokens.spaceSM),
                Expanded(
                  child: Text(
                    state.errorMessage!,
                    style:
                        text.hudCaption.copyWith(color: colors.textPrimary),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _InfoPanel extends StatelessWidget {
  const _InfoPanel();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AboutBloc, AboutState>(
      builder: (ctx, state) {
        final info = state.info;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Section(
              title: 'VERSIONS',
              rows: [
                _InfoRow(label: 'Backend', value: info?.backendVersion),
                _InfoRow(label: 'App', value: kAppVersion),
                _InfoRow(label: 'Firmware monture', value: info?.mountFirmware),
              ],
            ),
            const SizedBox(height: DesignTokens.spaceMD),
            _Section(
              title: 'RÉSEAU',
              rows: [
                _InfoRow(label: 'IP', value: info?.ip),
                _InfoRow(label: 'SSID', value: info?.ssid),
              ],
            ),
            const SizedBox(height: DesignTokens.spaceMD),
            _Section(
              title: 'SYSTÈME',
              rows: [
                _InfoRow(
                  label: 'Uptime',
                  value: info?.uptimeS != null
                      ? _formatUptime(info!.uptimeS!)
                      : null,
                ),
                _InfoRow(
                  label: 'Démarré le',
                  value: info?.startedAt != null
                      ? _formatStartedAt(info!.startedAt!)
                      : null,
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  /// Formate un uptime en secondes : "Xj Yh", "Xh Ym", "Xm Ys", "Xs".
  static String _formatUptime(int seconds) {
    if (seconds < 60) return '${seconds}s';
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    if (minutes < 60) return '${minutes}m ${secs}s';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    if (hours < 24) return '${hours}h ${mins}m';
    final days = hours ~/ 24;
    final hrs = hours % 24;
    return '${days}j ${hrs}h';
  }

  /// Parse une chaîne ISO 8601 et retourne la date/heure locale formatée.
  static String _formatStartedAt(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      String p(int n) => n.toString().padLeft(2, '0');
      return '${dt.year}-${p(dt.month)}-${p(dt.day)} '
          '${p(dt.hour)}:${p(dt.minute)}';
    } catch (_) {
      return iso;
    }
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.rows});

  final String title;
  final List<_InfoRow> rows;

  @override
  Widget build(BuildContext context) {
    final text = context.textStyles;
    final colors = context.colors;
    return HudPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            title,
            style: text.hudLabel.copyWith(color: colors.textMuted),
          ),
          const SizedBox(height: DesignTokens.spaceMD),
          ...rows,
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String? value;

  @override
  Widget build(BuildContext context) {
    final text = context.textStyles;
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceXS),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 140,
            child: Text(
              label,
              style: text.hudLabel.copyWith(color: colors.textMuted),
            ),
          ),
          Expanded(
            child: Text(
              value ?? '—',
              style: text.hudValue.copyWith(color: colors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _RefreshButton extends StatelessWidget {
  const _RefreshButton();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AboutBloc, AboutState>(
      builder: (ctx, state) {
        return SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: state.isLoading
                ? null
                : () =>
                    ctx.read<AboutBloc>().add(const AboutRefreshRequested()),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                vertical: DesignTokens.spaceMD,
              ),
              child: state.isLoading
                  ? SizedBox(
                      width: DesignTokens.iconSizeMD,
                      height: DesignTokens.iconSizeMD,
                      child: CircularProgressIndicator(
                        strokeWidth: DesignTokens.strokeRegular,
                        color: context.colors.accent,
                      ),
                    )
                  : Text('RAFRAÎCHIR', style: context.textStyles.hudBadge),
            ),
          ),
        );
      },
    );
  }
}
