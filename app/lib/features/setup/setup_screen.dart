import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/overall_status.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import 'network/network_screen.dart';
import 'widgets/setup_card.dart';

class SetupScreen extends StatelessWidget {
  const SetupScreen({super.key});

  SetupCard _cardForIndex(BuildContext ctx, int n) {
    return switch (n) {
      1 => const SetupCard(
          index: 1,
          icon: PhosphorIconsBold.scales,
          label: 'NIVEAU MONTURE',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      2 => const SetupCard(
          index: 2,
          icon: PhosphorIconsBold.compass,
          label: 'COMPASS',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      3 => const SetupCard(
          index: 3,
          icon: PhosphorIconsBold.arrowsVertical,
          label: 'ZÉRO ALT',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      4 => const SetupCard(
          index: 4,
          icon: PhosphorIconsBold.arrowsOutLineVertical,
          label: 'COURSES ALT',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      5 => const SetupCard(
          index: 5,
          icon: PhosphorIconsBold.arrowsClockwise,
          label: 'BACKLASH ALT',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      6 => const SetupCard(
          index: 6,
          icon: PhosphorIconsBold.arrowsClockwise,
          label: 'BACKLASH AZ',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      7 => const SetupCard(
          index: 7,
          icon: PhosphorIconsBold.arrowClockwise,
          label: 'CORDWRAP AZ',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
      8 => SetupCard(
          index: 8,
          icon: PhosphorIconsBold.wifiHigh,
          label: 'RÉSEAU',
          sublabel: 'IP Pi, hostname, Wi-Fi',
          dotStatus: OverallStatus.offline,
          onTap: () => Navigator.of(ctx).push(
            MaterialPageRoute(builder: (_) => const NetworkScreen()),
          ),
        ),
      9 => const SetupCard(
          index: 9,
          icon: PhosphorIconsBold.info,
          label: 'À PROPOS',
          sublabel: 'À implémenter (v0.2)',
          dotStatus: OverallStatus.offline,
        ),
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
