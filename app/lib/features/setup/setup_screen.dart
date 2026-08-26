import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/overall_status.dart';
import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'network/network_screen.dart';
import 'reference/almanac_screen.dart';
import 'reference/reference_models.dart';
import 'reference/reference_repository.dart';
import 'site/site_repository.dart';
import 'site/site_screen.dart';
import 'widgets/setup_card.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  /// Compteur incrémenté au retour de l'écran Site pour forcer le
  /// `FutureBuilder` à relire les coordonnées.
  int _siteRefresh = 0;

  Future<void> _openSite() async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => const SiteScreen()));
    if (mounted) {
      setState(() => _siteRefresh++);
    }
  }

  Widget _buildSiteCard() {
    return FutureBuilder<ObservingSite?>(
      key: ValueKey(_siteRefresh),
      future: SiteRepository(api: context.read<ApiService>()).getSite(),
      builder: (ctx, snap) {
        final site = snap.data;
        final sublabel = site == null
            ? 'Non défini'
            : formatCoords(site.lat, site.lon);
        final dot = site == null ? OverallStatus.gray : OverallStatus.green;

        return SetupCard(
          index: 1,
          icon: PhosphorIconsBold.mapPin,
          label: 'SITE',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openSite,
        );
      },
    );
  }

  Widget _buildAlmanacCard() {
    return FutureBuilder<ReferenceStatusDto>(
      future: context.read<ReferenceRepository>().getStatus(),
      builder: (ctx, snap) {
        final data = snap.data;
        final ready = data?.ready ?? false;
        final sublabel = data == null
            ? '—'
            : ready
                ? 'Couvre ${data.windowStart ?? '?'} → ${data.windowEnd ?? '?'}'
                : 'Indisponible — resynchroniser';
        final dot = ready ? OverallStatus.green : OverallStatus.gray;
        return SetupCard(
          index: 6,
          icon: PhosphorIconsBold.database,
          label: 'ALMANACH',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const AlmanacScreen()),
          ),
        );
      },
    );
  }

  SetupCard _placeholder(
    int n,
    IconData icon,
    String label, {
    String sublabel = 'À implémenter',
  }) => SetupCard(
    index: n,
    icon: icon,
    label: label,
    sublabel: sublabel,
    dotStatus: OverallStatus.gray,
  );

  Widget _cardForIndex(BuildContext ctx, int n) {
    return switch (n) {
      1 => _buildSiteCard(),
      // Backlash mount-side reporté : nécessite un patch du driver
      // indi_celestron_aux (MOUNT_AXIS_BACKLASH absent en v1.5) ; valeur réelle
      // seulement en imaging/guidage. Cf. ADR 2026-07-08. Rattaché Macro 5.
      2 => _placeholder(
        2,
        PhosphorIconsBold.arrowsClockwise,
        'BACKLASH ALT',
        sublabel: 'Reporté — Macro 5',
      ),
      3 => _placeholder(
        3,
        PhosphorIconsBold.arrowsClockwise,
        'BACKLASH AZ',
        sublabel: 'Reporté — Macro 5',
      ),
      4 => _placeholder(4, PhosphorIconsBold.arrowClockwise, 'CORDWRAP AZ'),
      5 => BlocBuilder<AppBloc, AppState>(
        buildWhen: (a, b) => a.connection != b.connection,
        builder: (innerCtx, state) => SetupCard(
          index: 5,
          icon: PhosphorIconsBold.wifiHigh,
          label: 'RÉSEAU',
          sublabel: switch (state.connection) {
            ConnectionStatus.connected => 'Pi joignable',
            ConnectionStatus.connecting => 'Connexion en cours…',
            ConnectionStatus.offline => 'Pi injoignable',
          },
          dotStatus: switch (state.connection) {
            ConnectionStatus.connected => OverallStatus.green,
            ConnectionStatus.connecting => OverallStatus.blue,
            ConnectionStatus.offline => OverallStatus.offline,
          },
          onTap: () => Navigator.of(
            ctx,
          ).push(MaterialPageRoute(builder: (_) => const NetworkScreen())),
        ),
      ),
      6 => _buildAlmanacCard(),
      _ => throw RangeError('index $n hors plage 1–6'),
    };
  }

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
            children: [
              const AstroAppBar(current: AstroScreen.setup),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: DesignTokens.spaceLG,
                  vertical: DesignTokens.spaceMD,
                ),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text('SETUP', style: text.hudLabel),
                ),
              ),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(
                    horizontal: DesignTokens.spaceLG,
                    vertical: DesignTokens.spaceSM,
                  ),
                  itemCount: 6,
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: DesignTokens.spaceMD),
                  itemBuilder: (ctx, i) => _cardForIndex(ctx, i + 1),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
