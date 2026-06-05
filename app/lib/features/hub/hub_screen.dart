import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:hugeicons/hugeicons.dart';

import '../../models/subsystem_states.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import '../about/about_screen.dart';
import '../alignment/alignment_wizard_screen.dart';
import '../catalogue/catalogue_screen.dart';
import '../manual/manual_screen.dart';
import '../setup/setup_screen.dart';
import '../system/system_screen.dart';
import 'widgets/hub_card.dart';

/// Hub central : landing post-Splash avec 6 cartes (MANUEL · ALIGNER ·
/// CATALOGUE · SETUP · STATUS · À PROPOS). Première carte en `primary`
/// variant. Macro 3 — item #1.
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
      // ALIGNER : hint dynamique selon disponibilité GPS Pi.
      // La carte reste tappable — le fallback téléphone est tenté au démarrage
      // du wizard. Le hint signale seulement l'absence de fix Pi.
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedTarget02,
        label: 'ALIGNER',
        hint: '3 étoiles · mise en station',
        builder: (_) => const AlignmentWizardScreen(),
        dynamicHint: _AlignmentHint.new,
      ),
      _HubEntry(
        heroIcon: HugeIcons.strokeRoundedStar,
        label: 'CATALOGUE',
        hint: 'Objets célestes · GoTo',
        builder: (_) => const CatalogueScreen(),
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
                    if (e.dynamicHint != null) {
                      return e.dynamicHint!(e);
                    }
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

/// Widget réactif pour la carte ALIGNER : affiche un hint contextuel selon
/// la disponibilité du GPS Pi (via AppBloc / SSE).
///
/// Si le GPS Pi a un fix (fix2d ou fix3d), le hint standard est affiché.
/// Sinon, un bandeau « Position GPS requise » est ajouté sous la carte —
/// miroir du pattern _NotAlignedBanner du CatalogueScreen.
///
/// La carte reste tappable dans tous les cas : le fallback GPS téléphone
/// est tenté au démarrage du wizard (AlignmentBloc._onStarted).
class _AlignmentHint extends StatelessWidget {
  const _AlignmentHint(this.entry);

  final _HubEntry entry;

  @override
  Widget build(BuildContext context) {
    return BlocSelector<AppBloc, AppState, bool>(
      selector: (state) {
        // Tant que l'état système n'est pas connu (null au démarrage), on ne
        // crie pas à l'absence de GPS. On n'affiche le bandeau que si on SAIT
        // qu'il n'y a pas de fix Pi.
        if (state.system == null) return true;
        final gps = state.system!.gps.state;
        return gps == GpsState.fix2d || gps == GpsState.fix3d;
      },
      builder: (context, hasPiGps) {
        final colors = context.colors;
        final text = context.textStyles;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            HubCard(
              heroIcon: entry.heroIcon,
              label: entry.label,
              hint: entry.hint,
              primary: entry.primary,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute(builder: entry.builder),
              ),
            ),
            if (!hasPiGps) ...[
              const SizedBox(height: DesignTokens.spaceXS),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: DesignTokens.spaceMD,
                  vertical: DesignTokens.spaceXS,
                ),
                decoration: BoxDecoration(
                  color: colors.dotWarn.withValues(alpha: 0.08),
                  border: Border.all(
                    color: colors.dotWarn.withValues(alpha: 0.35),
                  ),
                  borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
                ),
                child: Text(
                  'Position GPS requise — GPS Pi non disponible, '
                  'le GPS du téléphone sera utilisé.',
                  style: text.hudCaption.copyWith(color: colors.dotWarn),
                ),
              ),
            ],
          ],
        );
      },
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
    this.dynamicHint,
  });
  final List<List<dynamic>> heroIcon;
  final String label;
  final String hint;
  final WidgetBuilder builder;
  final bool primary;

  /// Si non null, ce builder remplace le [HubCard] standard pour cet item.
  final Widget Function(_HubEntry)? dynamicHint;
}
