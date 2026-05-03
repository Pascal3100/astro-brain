import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';

/// Placeholder — sera remplacé intégralement en Task 6 (NetworkScreen UI).
class NetworkScreen extends StatelessWidget {
  const NetworkScreen({super.key});

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
                padding: const EdgeInsets.all(DesignTokens.spaceLG),
                child: Text('RÉSEAU (TODO)', style: text.hudLabel),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
