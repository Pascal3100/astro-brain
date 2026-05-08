import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../manual_bloc.dart';

class RateControl extends StatelessWidget {
  const RateControl({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<ManualBloc, ManualState>(
      buildWhen: (a, b) => a.rate != b.rate,
      builder: (ctx, state) {
        return Row(
          children: [
            IconButton(
              onPressed: () =>
                  ctx.read<ManualBloc>().add(ManualRateChanged(state.rate - 1)),
              icon: PhosphorIcon(PhosphorIconsBold.minus,
                  color: colors.accent),
            ),
            Expanded(
              child: Row(
                children: List.generate(9, (i) {
                  final n = i + 1;
                  final active = n <= state.rate;
                  return Expanded(
                    child: Container(
                      margin: const EdgeInsets.symmetric(
                          horizontal: DesignTokens.spaceXXS),
                      height: DesignTokens.spaceLG,
                      decoration: BoxDecoration(
                        color: active
                            ? colors.accent
                            : colors.accent.withValues(alpha: 0.15),
                        borderRadius:
                            BorderRadius.circular(DesignTokens.radiusSM),
                      ),
                    ),
                  );
                }),
              ),
            ),
            IconButton(
              onPressed: () =>
                  ctx.read<ManualBloc>().add(ManualRateChanged(state.rate + 1)),
              icon: PhosphorIcon(PhosphorIconsBold.plus,
                  color: colors.accent),
            ),
            SizedBox(
              width: 28,
              child: Text('${state.rate}',
                  textAlign: TextAlign.center, style: text.hudValue),
            ),
          ],
        );
      },
    );
  }
}
