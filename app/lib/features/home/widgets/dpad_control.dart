import 'package:flutter/material.dart' hide Axis;
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../services/api_service.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../home_bloc.dart';

class DPadControl extends StatelessWidget {
  const DPadControl({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.connection != b.connection,
      builder: (ctx, app) {
        final disabled = app.connection != ConnectionStatus.connected;
        return Opacity(
          opacity: disabled ? 0.35 : 1,
          child: IgnorePointer(
            ignoring: disabled,
            child: GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              mainAxisSpacing: DesignTokens.spaceMD,
              crossAxisSpacing: DesignTokens.spaceMD,
              children: const [
                SizedBox(),
                _Btn(
                  icon: PhosphorIconsBold.caretUp,
                  axis: Axis.alt,
                  direction: Direction.plus,
                ),
                SizedBox(),
                _Btn(
                  icon: PhosphorIconsBold.caretLeft,
                  axis: Axis.az,
                  direction: Direction.minus,
                ),
                SizedBox(),
                _Btn(
                  icon: PhosphorIconsBold.caretRight,
                  axis: Axis.az,
                  direction: Direction.plus,
                ),
                SizedBox(),
                _Btn(
                  icon: PhosphorIconsBold.caretDown,
                  axis: Axis.alt,
                  direction: Direction.minus,
                ),
                SizedBox(),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Btn extends StatefulWidget {
  const _Btn({required this.icon, required this.axis, required this.direction});
  final IconData icon;
  final Axis axis;
  final Direction direction;

  @override
  State<_Btn> createState() => _BtnState();
}

class _BtnState extends State<_Btn> {
  bool _pressed = false;

  void _release() {
    if (!_pressed) return;
    setState(() => _pressed = false);
    context.read<HomeBloc>().add(HomeSlewReleased(widget.axis));
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return GestureDetector(
      onTapDown: (_) {
        setState(() => _pressed = true);
        context.read<HomeBloc>().add(
              HomeSlewPressed(axis: widget.axis, direction: widget.direction),
            );
      },
      onTapUp: (_) => _release(),
      onTapCancel: _release,
      child: AnimatedContainer(
        duration: DesignTokens.motionFast,
        curve: Curves.easeOut,
        decoration: BoxDecoration(
          color: Color.lerp(
            colors.bgGradientTop,
            colors.accent,
            _pressed ? 0.32 : 0.08,
          ),
          border: Border.all(
            color: colors.accent.withValues(alpha: _pressed ? 1 : 0.4),
            width: _pressed
                ? DesignTokens.strokeBold
                : DesignTokens.strokeRegular,
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          boxShadow: _pressed
              ? [
                  BoxShadow(
                    color: colors.accentGlow,
                    blurRadius: 16,
                    spreadRadius: 1,
                  ),
                ]
              : null,
        ),
        child: Center(
          child: PhosphorIcon(
            widget.icon,
            color: colors.accent,
            size: DesignTokens.iconSizeXL,
          ),
        ),
      ),
    );
  }
}
