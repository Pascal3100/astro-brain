import 'package:flutter/material.dart' hide Axis;
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import '../../widgets/dpad_control.dart';
import 'manual_bloc.dart';
import 'widgets/rate_control.dart';
import 'widgets/tracking_toggle.dart';

class ManualScreen extends StatelessWidget {
  const ManualScreen({super.key});

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
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              children: [
                const AstroAppBar(current: AstroScreen.manual),
                const SizedBox(height: DesignTokens.space2XL),
                const Expanded(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: _DPadHost(),
                    ),
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXL),
                const RateControl(),
                const SizedBox(height: DesignTokens.spaceXL),
                const TrackingToggle(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Wrapper stateless : gère la connexion + le mappage DPadDirection → Axis
// ---------------------------------------------------------------------------

/// Wraps [DPadControl] pour l'écran manuel :
/// - désactive visuellement le D-Pad quand l'app est hors ligne ;
/// - mappe [DPadDirection] → [Axis] / [Direction] et dispatche vers [ManualBloc].
class _DPadHost extends StatelessWidget {
  const _DPadHost();

  static Axis _axisOf(DPadDirection d) =>
      d == DPadDirection.up || d == DPadDirection.down ? Axis.alt : Axis.az;

  static (Axis, Direction) _map(DPadDirection d) => switch (d) {
        DPadDirection.up => (Axis.alt, Direction.plus),
        DPadDirection.down => (Axis.alt, Direction.minus),
        DPadDirection.left => (Axis.az, Direction.minus),
        DPadDirection.right => (Axis.az, Direction.plus),
      };

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.connection != b.connection,
      builder: (ctx, app) {
        final bloc = ctx.read<ManualBloc>();
        final disabled = app.connection != ConnectionStatus.connected;
        return Opacity(
          opacity: disabled ? 0.35 : 1,
          child: IgnorePointer(
            ignoring: disabled,
            child: DPadControl(
              onPress: (d) {
                final (axis, direction) = _map(d);
                bloc.add(ManualSlewPressed(axis: axis, direction: direction));
              },
              onRelease: (d) => bloc.add(ManualSlewReleased(_axisOf(d))),
            ),
          ),
        );
      },
    );
  }
}
