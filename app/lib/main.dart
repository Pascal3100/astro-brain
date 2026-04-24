import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'theme/app_colors.dart';
import 'theme/app_typography.dart';
import 'theme/astro_theme.dart';
import 'theme/design_tokens.dart';
import 'theme/theme_cubit.dart';

void main() {
  runApp(const AstroBrainApp());
}

/// Racine de l'app Astro-Brain.
///
/// Fournit le [ThemeCubit] à tout l'arbre, puis bascule entre le thème jour
/// et nuit selon l'état du Cubit. On utilise `ThemeMode.light` pour jour et
/// `ThemeMode.dark` pour nuit afin de rester dans l'idiome Flutter — mais
/// visuellement les deux thèmes sont sur fond sombre.
class AstroBrainApp extends StatelessWidget {
  const AstroBrainApp({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<ThemeCubit>(
      create: (_) => ThemeCubit(),
      child: BlocBuilder<ThemeCubit, AstroThemeMode>(
        builder: (context, mode) {
          return MaterialApp(
            title: 'Astro-Brain',
            debugShowCheckedModeBanner: false,
            theme: AstroTheme.buildDay(),
            darkTheme: AstroTheme.buildNight(),
            themeMode:
                mode == AstroThemeMode.day ? ThemeMode.light : ThemeMode.dark,
            home: const _ThemePreviewScreen(),
          );
        },
      ),
    );
  }
}

/// Écran provisoire de preview du thème — valide que tous les tokens,
/// couleurs sémantiques et styles HUD sont bien exposés et rendus.
///
/// Sera remplacé par la vraie `SplashScreen` + `HomeScreen` dans les plans
/// suivants.
class _ThemePreviewScreen extends StatelessWidget {
  const _ThemePreviewScreen();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final mode = context.watch<ThemeCubit>().state;

    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: Text('ASTRO-BRAIN', style: text.hudLabel.copyWith(fontSize: 13)),
        actions: [
          IconButton(
            tooltip: mode == AstroThemeMode.day
                ? 'Passer en mode nuit'
                : 'Passer en mode jour',
            icon: PhosphorIcon(
              mode == AstroThemeMode.day
                  ? PhosphorIconsBold.moon
                  : PhosphorIconsBold.sun,
              color: colors.accent,
            ),
            onPressed: () => context.read<ThemeCubit>().toggle(),
          ),
          const SizedBox(width: DesignTokens.spaceSM),
        ],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            children: [
              const SizedBox(height: DesignTokens.spaceXL),
              _SectionTitle('DOTS D\'ÉTAT'),
              const SizedBox(height: DesignTokens.spaceMD),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _Dot(color: colors.dotOk, label: 'OK'),
                  _Dot(color: colors.dotTransition, label: 'TRANSITION'),
                  _Dot(color: colors.dotWarn, label: 'WARN'),
                  _Dot(color: colors.dotError, label: 'ERROR'),
                ],
              ),
              const SizedBox(height: DesignTokens.space2XL),
              _SectionTitle('TYPOGRAPHIE'),
              const SizedBox(height: DesignTokens.spaceMD),
              Text('Inter — display',
                  style: Theme.of(context).textTheme.displaySmall),
              const SizedBox(height: DesignTokens.spaceSM),
              Text('Inter — body',
                  style: Theme.of(context).textTheme.bodyLarge),
              const SizedBox(height: DesignTokens.spaceLG),
              Text('HUD LABEL', style: text.hudLabel),
              const SizedBox(height: DesignTokens.spaceXS),
              Text('HUD VALUE — Fix 3D · 14 sats', style: text.hudValue),
              const SizedBox(height: DesignTokens.spaceXS),
              Text('hud caption — depuis 12 s', style: text.hudCaption),
              const SizedBox(height: DesignTokens.space2XL),
              _SectionTitle('BOUTONS'),
              const SizedBox(height: DesignTokens.spaceMD),
              Row(
                children: [
                  FilledButton(onPressed: () {}, child: const Text('RETRY')),
                  const SizedBox(width: DesignTokens.spaceMD),
                  OutlinedButton(
                    onPressed: () {},
                    child: const Text('CONTINUE OFFLINE →'),
                  ),
                ],
              ),
              const SizedBox(height: DesignTokens.space2XL),
              _SectionTitle('CARD HUD'),
              const SizedBox(height: DesignTokens.spaceMD),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(DesignTokens.spaceLG),
                  child: Row(
                    children: [
                      PhosphorIcon(
                        PhosphorIconsBold.gpsFix,
                        color: colors.accent,
                        size: DesignTokens.iconSizeLG,
                      ),
                      const SizedBox(width: DesignTokens.spaceLG),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('GPS', style: text.hudLabel),
                            const SizedBox(height: DesignTokens.spaceXXS),
                            Text('Fix 3D · 14 sats · HDOP 0.83',
                                style: text.hudValue),
                          ],
                        ),
                      ),
                      Container(
                        width: DesignTokens.statusDotSize,
                        height: DesignTokens.statusDotSize,
                        decoration: BoxDecoration(
                          color: colors.dotOk,
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                                color: colors.dotOk, blurRadius: 8, spreadRadius: 0)
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: DesignTokens.space2XL),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Row(
      children: [
        Text(text,
            style: context.textStyles.hudBadge.copyWith(color: colors.accent)),
        const SizedBox(width: DesignTokens.spaceMD),
        Expanded(
          child: Container(
            height: DesignTokens.strokeThin,
            color: colors.accent.withValues(alpha: 0.25),
          ),
        ),
      ],
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color, required this.label});
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: DesignTokens.statusDotSizeLg,
          height: DesignTokens.statusDotSizeLg,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(color: color, blurRadius: 12, spreadRadius: 1),
            ],
          ),
        ),
        const SizedBox(height: DesignTokens.spaceSM),
        Text(label, style: context.textStyles.hudCaption),
      ],
    );
  }
}
