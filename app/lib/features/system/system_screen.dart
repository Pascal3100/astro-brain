import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/overall_status.dart';
import '../../models/subsystem_state.dart';
import '../../models/subsystem_states.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../utils/mount_error_messages.dart';
import 'widgets/subsystem_card.dart';

class SystemScreen extends StatelessWidget {
  const SystemScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: PhosphorIcon(PhosphorIconsBold.caretLeft, color: colors.accent),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text('SYSTEM', style: text.hudLabel.copyWith(fontSize: 13)),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: BlocBuilder<AppBloc, AppState>(
          builder: (ctx, state) {
            final sys = state.system;
            if (sys == null) {
              return Center(
                child: Text('NO STATE', style: text.hudLabel),
              );
            }
            return ListView(
              padding: const EdgeInsets.all(DesignTokens.spaceLG),
              children: [
                SubsystemCard(
                  label: 'MOUNT',
                  icon: PhosphorIconsBold.arrowsOutCardinal,
                  stateLabel: sys.mount.state.name.toUpperCase(),
                  detailsText: _mountDetails(sys.mount),
                  since: sys.mount.since,
                  dotStatus: _mountDot(sys.mount.state),
                  message: humanizeMountMessage(sys.mount.message),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'GPS',
                  icon: PhosphorIconsBold.gpsFix,
                  stateLabel: sys.gps.state.name.toUpperCase(),
                  detailsText: _gpsDetails(sys.gps),
                  since: sys.gps.since,
                  dotStatus: _gpsDot(sys.gps.state),
                  message: sys.gps.message,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'TRACKING',
                  icon: PhosphorIconsBold.crosshairSimple,
                  stateLabel: sys.tracking.state.name.toUpperCase(),
                  detailsText: '',
                  since: sys.tracking.since,
                  dotStatus: sys.tracking.state == TrackingState.sidereal
                      ? OverallStatus.green
                      : OverallStatus.orange,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'NETWORK',
                  icon: PhosphorIconsBold.wifiHigh,
                  stateLabel: sys.network.state.name.toUpperCase(),
                  detailsText: _networkDetails(sys.network),
                  since: sys.network.since,
                  dotStatus: sys.network.state == NetworkState.offline
                      ? OverallStatus.orange
                      : OverallStatus.green,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'SYSTEM',
                  icon: sys.system.state == SystemInfoState.ok
                      ? PhosphorIconsBold.cpu
                      : PhosphorIconsBold.thermometerSimple,
                  stateLabel: sys.system.state.name.toUpperCase(),
                  detailsText: _systemDetails(sys.system),
                  since: sys.system.since,
                  dotStatus: switch (sys.system.state) {
                    SystemInfoState.ok => OverallStatus.green,
                    SystemInfoState.warning => OverallStatus.orange,
                    SystemInfoState.critical => OverallStatus.red,
                  },
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  String _mountDetails(SubsystemState<MountState> s) {
    final fw = s.details['firmware_version'];
    return fw == null ? '' : 'firmware $fw';
  }

  String _gpsDetails(SubsystemState<GpsState> s) {
    final lat = s.details['lat'];
    final lon = s.details['lon'];
    final sats = s.details['satellites'];
    if (lat == null || lon == null) return 'sats=${sats ?? 0}';
    return '${(lat as num).toStringAsFixed(4)} / ${(lon as num).toStringAsFixed(4)} · $sats sats';
  }

  String _networkDetails(SubsystemState<NetworkState> s) {
    final ssid = s.details['ssid'];
    final ip = s.details['ip'];
    if (ssid == null && ip == null) return '';
    return '$ssid · $ip';
  }

  String _systemDetails(SubsystemState<SystemInfoState> s) {
    final t = s.details['cpu_temp_c'];
    final load = s.details['cpu_load'];
    return '$t°C · load $load';
  }

  OverallStatus _mountDot(MountState s) => switch (s) {
        MountState.ready || MountState.moving => OverallStatus.green,
        MountState.connecting => OverallStatus.blue,
        MountState.disconnected || MountState.error => OverallStatus.red,
      };

  OverallStatus _gpsDot(GpsState s) => switch (s) {
        GpsState.fix3d || GpsState.fix2d => OverallStatus.green,
        GpsState.searching => OverallStatus.blue,
        GpsState.off || GpsState.noFix => OverallStatus.orange,
      };
}
