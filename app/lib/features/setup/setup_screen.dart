import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/calibration.dart';
import '../../models/overall_status.dart';
import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'calibration/lis3mdl_screen.dart';
import 'network/network_screen.dart';
import 'reference/almanac_screen.dart';
import 'reference/reference_models.dart';
import 'reference/reference_repository.dart';
import 'widgets/setup_card.dart';

/// Formate une durée écoulée pour le sublabel "Calibré il y a Xs/min/h/j".
String formatRelativeAge(Duration d) {
  if (d.inSeconds < 60) return 'Calibré il y a ${d.inSeconds}s';
  if (d.inMinutes < 60) return 'Calibré il y a ${d.inMinutes}min';
  if (d.inHours < 24) return 'Calibré il y a ${d.inHours}h';
  return 'Calibré il y a ${d.inDays}j';
}

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  /// Compteur incrémenté à chaque retour de l'écran de calibration #1
  /// (compass LIS3MDL) pour forcer le `FutureBuilder` à re-fetcher le statut.
  int _lis3mdlRefresh = 0;

  Future<void> _openLis3mdl() async {
    final didCalibrate = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => const Lis3mdlScreen()));
    if (didCalibrate == true && mounted) {
      setState(() => _lis3mdlRefresh++);
    }
  }

  Widget _buildLis3mdlCard() {
    return FutureBuilder<CalibrationStatus>(
      key: ValueKey(_lis3mdlRefresh),
      future: context.read<ApiService>().getCalibrationStatus('lis3mdl'),
      builder: (ctx, snap) {
        final calibratedAt = snap.data?.calibratedAt;
        final isCalibrated = calibratedAt != null;
        final sublabel = isCalibrated
            ? formatRelativeAge(DateTime.now().difference(calibratedAt))
            : 'Non calibré';
        final dot = isCalibrated ? OverallStatus.green : OverallStatus.gray;

        return SetupCard(
          index: 1,
          icon: PhosphorIconsBold.compass,
          label: 'COMPASS',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openLis3mdl,
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
      1 => _buildLis3mdlCard(),
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
