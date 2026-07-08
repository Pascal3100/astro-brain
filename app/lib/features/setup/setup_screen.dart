import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/calibration.dart';
import '../../models/limits.dart';
import '../../models/overall_status.dart';
import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'calibration/adxl_mount_screen.dart';
import 'calibration/adxl_tube_screen.dart';
import 'calibration/lis3mdl_screen.dart';
import 'limits/limits_screen.dart';
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

  /// Idem pour la card #3 (ADXL tube — zéro ALT).
  int _adxlTubeRefresh = 0;

  /// Idem pour la card #4 (courses ALT).
  int _limitsAltRefresh = 0;

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

  Future<void> _openAdxlTube() async {
    final didCalibrate = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => const AdxlTubeScreen()));
    if (didCalibrate == true && mounted) {
      setState(() => _adxlTubeRefresh++);
    }
  }

  Future<void> _openLimitsAlt() async {
    final didSave = await Navigator.of(
      context,
    ).push<bool>(MaterialPageRoute(builder: (_) => const LimitsAltScreen()));
    if (didSave == true && mounted) {
      setState(() => _limitsAltRefresh++);
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

  Widget _buildAdxlTubeCard() {
    return FutureBuilder<CalibrationStatus>(
      key: ValueKey(_adxlTubeRefresh),
      future: context.read<ApiService>().getCalibrationStatus('adxl345_tube'),
      builder: (ctx, snap) {
        final calibratedAt = snap.data?.calibratedAt;
        final isCalibrated = calibratedAt != null;
        final sublabel = isCalibrated
            ? formatRelativeAge(DateTime.now().difference(calibratedAt))
            : 'Non calibré';
        final dot = isCalibrated ? OverallStatus.green : OverallStatus.gray;

        return SetupCard(
          index: 3,
          icon: PhosphorIconsBold.arrowsVertical,
          label: 'ZÉRO ALT',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openAdxlTube,
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

  Widget _buildLimitsAltCard() {
    return FutureBuilder<AltLimits?>(
      key: ValueKey(_limitsAltRefresh),
      future: context.read<ApiService>().getAltLimits(),
      builder: (ctx, snap) {
        final limits = snap.data;
        final isSet = limits != null;
        final sublabel = isSet
            ? 'min ${limits.minDeg.round()}° / max ${limits.maxDeg.round()}°'
            : 'Non défini';
        final dot = isSet ? OverallStatus.green : OverallStatus.gray;

        return SetupCard(
          index: 4,
          icon: PhosphorIconsBold.arrowsOutLineVertical,
          label: 'COURSES ALT',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: _openLimitsAlt,
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
      1 => _buildAdxlMountCard(),
      2 => _buildLis3mdlCard(),
      3 => _buildAdxlTubeCard(),
      4 => _buildLimitsAltCard(),
      // Backlash mount-side reporté : nécessite un patch du driver
      // indi_celestron_aux (MOUNT_AXIS_BACKLASH absent en v1.5) ; valeur réelle
      // seulement en imaging/guidage. Cf. ADR 2026-07-08. Rattaché Macro 5.
      5 => _placeholder(
        5,
        PhosphorIconsBold.arrowsClockwise,
        'BACKLASH ALT',
        sublabel: 'Reporté — Macro 5',
      ),
      6 => _placeholder(
        6,
        PhosphorIconsBold.arrowsClockwise,
        'BACKLASH AZ',
        sublabel: 'Reporté — Macro 5',
      ),
      7 => _placeholder(7, PhosphorIconsBold.arrowClockwise, 'CORDWRAP AZ'),
      8 => BlocBuilder<AppBloc, AppState>(
        buildWhen: (a, b) => a.connection != b.connection,
        builder: (innerCtx, state) => SetupCard(
          index: 8,
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
      _ => throw RangeError('index $n hors plage 1–8'),
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
                  itemCount: 8,
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
