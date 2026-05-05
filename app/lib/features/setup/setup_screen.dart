import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/calibration.dart';
import '../../models/overall_status.dart';
import '../../services/api_service.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'calibration/adxl_mount_screen.dart';
import 'calibration/lis3mdl_screen.dart';
import 'network/network_screen.dart';
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
  /// pour forcer le `FutureBuilder` à re-fetcher le statut.
  int _adxlMountRefresh = 0;

  /// Idem pour la card #2 (compass LIS3MDL).
  int _lis3mdlRefresh = 0;

  Future<void> _openAdxlMount() async {
    final didCalibrate = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => const AdxlMountScreen()));
    if (didCalibrate == true && mounted) {
      setState(() => _adxlMountRefresh++);
    }
  }

  Future<void> _openLis3mdl() async {
    final didCalibrate = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => const Lis3mdlScreen()));
    if (didCalibrate == true && mounted) {
      setState(() => _lis3mdlRefresh++);
    }
  }

  Widget _buildAdxlMountCard() {
    return FutureBuilder<CalibrationStatus>(
      key: ValueKey(_adxlMountRefresh),
      future: context.read<ApiService>().getCalibrationStatus('adxl345_mount'),
      builder: (ctx, snap) {
        final calibratedAt = snap.data?.calibratedAt;
        final isCalibrated = calibratedAt != null;
        final sublabel = isCalibrated
            ? formatRelativeAge(DateTime.now().difference(calibratedAt))
            : 'Non calibré';
        final dot = isCalibrated ? OverallStatus.green : OverallStatus.gray;

        return SetupCard(
          index: 1,
          icon: PhosphorIconsBold.scales,
          label: 'NIVEAU MONTURE',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openAdxlMount,
        );
      },
    );
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
          index: 2,
          icon: PhosphorIconsBold.compass,
          label: 'COMPASS',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openLis3mdl,
        );
      },
    );
  }

  SetupCard _placeholder(int n, IconData icon, String label) => SetupCard(
    index: n,
    icon: icon,
    label: label,
    sublabel: 'À implémenter (v0.2)',
    dotStatus: OverallStatus.gray,
  );

  Widget _cardForIndex(BuildContext ctx, int n) {
    return switch (n) {
      1 => _buildAdxlMountCard(),
      2 => _buildLis3mdlCard(),
      3 => _placeholder(3, PhosphorIconsBold.arrowsVertical, 'ZÉRO ALT'),
      4 => _placeholder(
        4,
        PhosphorIconsBold.arrowsOutLineVertical,
        'COURSES ALT',
      ),
      5 => _placeholder(5, PhosphorIconsBold.arrowsClockwise, 'BACKLASH ALT'),
      6 => _placeholder(6, PhosphorIconsBold.arrowsClockwise, 'BACKLASH AZ'),
      7 => _placeholder(7, PhosphorIconsBold.arrowClockwise, 'CORDWRAP AZ'),
      8 => SetupCard(
        index: 8,
        icon: PhosphorIconsBold.wifiHigh,
        label: 'RÉSEAU',
        sublabel: 'Override host/port app',
        dotStatus: OverallStatus.green,
        onTap: () => Navigator.of(
          ctx,
        ).push(MaterialPageRoute(builder: (_) => const NetworkScreen())),
      ),
      9 => _placeholder(9, PhosphorIconsBold.info, 'À PROPOS'),
      _ => throw RangeError('index $n hors plage 1–9'),
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
                  itemCount: 9,
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
