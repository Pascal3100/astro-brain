import 'package:flutter/material.dart';

import 'design_tokens.dart';

/// Couleurs sémantiques spécifiques à l'app Astro-Brain.
///
/// Ces slots n'existent pas dans le [ColorScheme] Material 3 :
/// - `accent` / `accentGlow` : couleur signature (bleu jour, rouge nuit) + halo
/// - `bgGradientTop` / `bgGradientBottom` : fond HUD en dégradé
/// - `grid` : grille technique subtile sur le fond
/// - `textPrimary` / `textMuted` : teintes texte spécifiques au HUD
/// - `dotOk` / `dotTransition` / `dotWarn` / `dotError` : pastilles d'état
///   (🟢🔵🟠🔴 jour, nuances de rouge uniquement la nuit)
///
/// Usage :
/// ```dart
/// final colors = Theme.of(context).extension<AppColors>()!;
/// Container(color: colors.bgGradientTop);
/// ```
@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.accent,
    required this.accentGlow,
    required this.bgGradientTop,
    required this.bgGradientBottom,
    required this.grid,
    required this.textPrimary,
    required this.textMuted,
    required this.dotOk,
    required this.dotTransition,
    required this.dotWarn,
    required this.dotError,
  });

  final Color accent;
  final Color accentGlow;
  final Color bgGradientTop;
  final Color bgGradientBottom;
  final Color grid;
  final Color textPrimary;
  final Color textMuted;
  final Color dotOk;
  final Color dotTransition;
  final Color dotWarn;
  final Color dotError;

  static const AppColors day = AppColors(
    accent: DesignTokens.dayAccent,
    accentGlow: DesignTokens.dayAccentGlow,
    bgGradientTop: DesignTokens.dayBgTop,
    bgGradientBottom: DesignTokens.dayBgBottom,
    grid: DesignTokens.dayGrid,
    textPrimary: DesignTokens.dayText,
    textMuted: DesignTokens.dayTextMuted,
    dotOk: DesignTokens.dayDotOk,
    dotTransition: DesignTokens.dayDotTransition,
    dotWarn: DesignTokens.dayDotWarn,
    dotError: DesignTokens.dayDotError,
  );

  static const AppColors night = AppColors(
    accent: DesignTokens.nightAccent,
    accentGlow: DesignTokens.nightAccentGlow,
    bgGradientTop: DesignTokens.nightBgTop,
    bgGradientBottom: DesignTokens.nightBgBottom,
    grid: DesignTokens.nightGrid,
    textPrimary: DesignTokens.nightText,
    textMuted: DesignTokens.nightTextMuted,
    dotOk: DesignTokens.nightDotOk,
    dotTransition: DesignTokens.nightDotTransition,
    dotWarn: DesignTokens.nightDotWarn,
    dotError: DesignTokens.nightDotError,
  );

  @override
  AppColors copyWith({
    Color? accent,
    Color? accentGlow,
    Color? bgGradientTop,
    Color? bgGradientBottom,
    Color? grid,
    Color? textPrimary,
    Color? textMuted,
    Color? dotOk,
    Color? dotTransition,
    Color? dotWarn,
    Color? dotError,
  }) {
    return AppColors(
      accent: accent ?? this.accent,
      accentGlow: accentGlow ?? this.accentGlow,
      bgGradientTop: bgGradientTop ?? this.bgGradientTop,
      bgGradientBottom: bgGradientBottom ?? this.bgGradientBottom,
      grid: grid ?? this.grid,
      textPrimary: textPrimary ?? this.textPrimary,
      textMuted: textMuted ?? this.textMuted,
      dotOk: dotOk ?? this.dotOk,
      dotTransition: dotTransition ?? this.dotTransition,
      dotWarn: dotWarn ?? this.dotWarn,
      dotError: dotError ?? this.dotError,
    );
  }

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    return AppColors(
      accent: Color.lerp(accent, other.accent, t)!,
      accentGlow: Color.lerp(accentGlow, other.accentGlow, t)!,
      bgGradientTop: Color.lerp(bgGradientTop, other.bgGradientTop, t)!,
      bgGradientBottom:
          Color.lerp(bgGradientBottom, other.bgGradientBottom, t)!,
      grid: Color.lerp(grid, other.grid, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      dotOk: Color.lerp(dotOk, other.dotOk, t)!,
      dotTransition: Color.lerp(dotTransition, other.dotTransition, t)!,
      dotWarn: Color.lerp(dotWarn, other.dotWarn, t)!,
      dotError: Color.lerp(dotError, other.dotError, t)!,
    );
  }
}

/// Raccourci pour accéder aux couleurs sémantiques depuis un BuildContext.
extension AppColorsX on BuildContext {
  AppColors get colors => Theme.of(this).extension<AppColors>()!;
}
