import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import '../about/about_screen.dart';
import '../alignment/alignment_wizard_screen.dart';
import '../manual/manual_screen.dart';
import '../setup/setup_screen.dart';
import '../system/system_screen.dart';
import 'widgets/hub_card.dart';

/// Hub central : landing post-Splash avec 5 cartes (MANUEL · ALIGNER · SETUP ·
/// STATUS · À PROPOS). Première carte en `primary` variant. Macro 3 — item #1.
class HubScreen extends StatelessWidget {
  const HubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    final entries = <_HubEntry>[
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedJoystick01,
        label: 'MANUEL',
        hint: 'Joystick · piloter la monture',
        primary: true,
        builder: (_) => const ManualScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedTarget02,
        label: 'ALIGNER',
        hint: '3 étoiles · mise en station',
        builder: (_) => const AlignmentWizardScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedSettings02,
        label: 'SETUP',
        hint: 'Calibration · niveau · réseau',
        builder: (_) => const SetupScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedRadar01,
        label: 'STATUS',
        hint: 'Indicateurs · capteurs · mount',
        builder: (_) => const SystemScreen(),
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedInformationCircle,
        label: 'À PROPOS',
        hint: 'Versions · uptime · système',
        builder: (_) => const AboutScreen(),
      ),
    ];

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
              const AstroAppBar(current: AstroScreen.hub),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  DesignTokens.spaceLG,
                  DesignTokens.space2XL,
                  DesignTokens.spaceLG,
                  DesignTokens.spaceLG,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '// ASTRO-BRAIN',
                      style: text.hudLabel.copyWith(
                        color: colors.accent.withValues(alpha: 0.6),
                      ),
                    ),
                    const SizedBox(height: DesignTokens.spaceXS),
                    Text(
                      'Que fait-on ce soir ?',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: colors.textPrimary,
                            fontWeight: FontWeight.w500,
                          ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(
                    horizontal: DesignTokens.spaceLG,
                  ),
                  itemCount: entries.length,
                  separatorBuilder: (_, _) =>
                      const SizedBox(height: DesignTokens.spaceMD),
                  itemBuilder: (ctx, i) {
                    final e = entries[i];
                    return HubCard(
                      heroIcon: e.heroIcon,
                      label: e.label,
                      hint: e.hint,
                      primary: e.primary,
                      onTap: () => Navigator.of(ctx).push(
                        MaterialPageRoute(builder: e.builder),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HubEntry {
  const _HubEntry({
    required this.heroIcon,
    required this.label,
    required this.hint,
    required this.builder,
    this.primary = false,
  });
  final List<List<dynamic>> heroIcon;
  final String label;
  final String hint;
  final WidgetBuilder builder;
  final bool primary;
}
