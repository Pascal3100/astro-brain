import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Construit le [TextTheme] Material 3 en **Inter** pour tout le texte
/// d'interface général. Les couleurs sont appliquées via [color].
///
/// Les styles HUD monospace (labels techniques, valeurs numériques) sont
/// exposés à part via [AppTextStyles].
TextTheme buildInterTextTheme({required Color color}) {
  final base = GoogleFonts.interTextTheme(
    ThemeData(brightness: Brightness.dark).textTheme,
  );
  return base.apply(bodyColor: color, displayColor: color);
}

/// Styles de texte spécifiques au HUD Astro-Brain, en **JetBrains Mono**.
///
/// Philosophie :
/// - `hudLabel` : libellés techniques type `MOUNT`, `GPS`, `TRACKING` (uppercase, letter-spacing).
/// - `hudValue` : valeurs numériques/alphanumériques importantes (`Ready`, `Fix 3D`, `v11.01`).
/// - `hudCaption` : infos secondaires (`depuis 2 min`, `8 sats`).
/// - `hudBadge` : texte à l'intérieur d'une pastille/chip.
///
/// Usage :
/// ```dart
/// Text('MOUNT', style: context.textStyles.hudLabel);
/// ```
@immutable
class AppTextStyles extends ThemeExtension<AppTextStyles> {
  const AppTextStyles({
    required this.hudLabel,
    required this.hudValue,
    required this.hudCaption,
    required this.hudBadge,
  });

  final TextStyle hudLabel;
  final TextStyle hudValue;
  final TextStyle hudCaption;
  final TextStyle hudBadge;

  /// Construit les styles HUD pour une couleur de texte donnée.
  /// La couleur doit venir de [AppColors.textPrimary] pour rester cohérent
  /// avec le thème courant.
  factory AppTextStyles.build({required Color color}) {
    TextStyle mono(
      double size,
      FontWeight weight, {
      double? letterSpacing,
      double? height,
    }) =>
        GoogleFonts.jetBrainsMono(
          fontSize: size,
          fontWeight: weight,
          color: color,
          letterSpacing: letterSpacing,
          height: height,
        );

    return AppTextStyles(
      hudLabel: mono(11, FontWeight.w500, letterSpacing: 1.4, height: 1.2),
      hudValue: mono(14, FontWeight.w500, letterSpacing: 0.4, height: 1.3),
      hudCaption: mono(11, FontWeight.w400, letterSpacing: 0.3, height: 1.2),
      hudBadge: mono(10, FontWeight.w700, letterSpacing: 1.2, height: 1.0),
    );
  }

  @override
  AppTextStyles copyWith({
    TextStyle? hudLabel,
    TextStyle? hudValue,
    TextStyle? hudCaption,
    TextStyle? hudBadge,
  }) {
    return AppTextStyles(
      hudLabel: hudLabel ?? this.hudLabel,
      hudValue: hudValue ?? this.hudValue,
      hudCaption: hudCaption ?? this.hudCaption,
      hudBadge: hudBadge ?? this.hudBadge,
    );
  }

  @override
  AppTextStyles lerp(ThemeExtension<AppTextStyles>? other, double t) {
    if (other is! AppTextStyles) return this;
    return AppTextStyles(
      hudLabel: TextStyle.lerp(hudLabel, other.hudLabel, t)!,
      hudValue: TextStyle.lerp(hudValue, other.hudValue, t)!,
      hudCaption: TextStyle.lerp(hudCaption, other.hudCaption, t)!,
      hudBadge: TextStyle.lerp(hudBadge, other.hudBadge, t)!,
    );
  }
}

/// Raccourci pour accéder aux styles HUD depuis un BuildContext.
extension AppTextStylesX on BuildContext {
  AppTextStyles get textStyles => Theme.of(this).extension<AppTextStyles>()!;
}
