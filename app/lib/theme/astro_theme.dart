import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_typography.dart';
import 'design_tokens.dart';

/// Fabrique des [ThemeData] Astro-Brain (Material 3).
///
/// Deux thèmes :
/// - [buildDay] — palette bleu spatial, pour l'usage en condition normale
/// - [buildNight] — palette rouge astro, pour la préservation de la vision
///   nocturne (aucun bleu ni vert)
///
/// Les deux sont en `Brightness.dark` visuellement : le toggle jour/nuit n'est
/// PAS un toggle clair/sombre, c'est un changement de **teinte d'accent**.
/// On expose tout de même `ThemeMode.light` pour le mode jour et
/// `ThemeMode.dark` pour le mode nuit, afin de rester dans l'idiome Flutter
/// (`MaterialApp(theme: buildDay(), darkTheme: buildNight(), themeMode: ...)`).
class AstroTheme {
  AstroTheme._();

  /// Mode jour — accent bleu, fond bleu très sombre.
  static ThemeData buildDay() => _build(colors: AppColors.day);

  /// Mode nuit — accent rouge, fond rouge très sombre, aucun bleu ni vert.
  static ThemeData buildNight() => _build(colors: AppColors.night);

  static ThemeData _build({required AppColors colors}) {
    final colorScheme = ColorScheme(
      brightness: Brightness.dark,
      primary: colors.accent,
      onPrimary: colors.bgGradientTop,
      secondary: colors.accent,
      onSecondary: colors.bgGradientTop,
      tertiary: colors.dotTransition,
      onTertiary: colors.bgGradientTop,
      error: colors.dotError,
      onError: Colors.white,
      surface: colors.bgGradientTop,
      onSurface: colors.textPrimary,
      surfaceContainerLowest: colors.bgGradientBottom,
      surfaceContainerLow: _blend(colors.bgGradientTop, colors.accent, 0.04),
      surfaceContainer: _blend(colors.bgGradientTop, colors.accent, 0.06),
      surfaceContainerHigh: _blend(colors.bgGradientTop, colors.accent, 0.08),
      surfaceContainerHighest:
          _blend(colors.bgGradientTop, colors.accent, 0.12),
      outline: colors.textMuted,
      outlineVariant: _withAlpha(colors.accent, 0.25),
      shadow: Colors.black,
      scrim: Colors.black,
      inverseSurface: colors.textPrimary,
      onInverseSurface: colors.bgGradientTop,
      inversePrimary: colors.accentGlow,
    );

    final textTheme = buildInterTextTheme(color: colors.textPrimary);
    final textStyles = AppTextStyles.build(color: colors.textPrimary);

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colors.bgGradientTop,
      canvasColor: colors.bgGradientTop,
      textTheme: textTheme,
      iconTheme: IconThemeData(
        color: colors.textPrimary,
        size: DesignTokens.iconSizeMD,
      ),
      dividerTheme: DividerThemeData(
        color: _withAlpha(colors.accent, 0.15),
        thickness: DesignTokens.strokeThin,
        space: DesignTokens.spaceLG,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: colors.accent,
          foregroundColor: colors.bgGradientTop,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: DesignTokens.spaceLG,
            vertical: DesignTokens.spaceMD,
          ),
          textStyle: textStyles.hudBadge,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: colors.accent,
          side: BorderSide(
            color: colors.accent,
            width: DesignTokens.strokeRegular,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: DesignTokens.spaceLG,
            vertical: DesignTokens.spaceMD,
          ),
          textStyle: textStyles.hudBadge,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: colors.accent,
          textStyle: textStyles.hudBadge,
        ),
      ),
      cardTheme: CardThemeData(
        color: _blend(colors.bgGradientTop, colors.accent, 0.04),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          side: BorderSide(
            color: _withAlpha(colors.accent, 0.2),
            width: DesignTokens.strokeThin,
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusLG),
        ),
        margin: EdgeInsets.zero,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: colors.textPrimary,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: textStyles.hudLabel.copyWith(fontSize: 13),
      ),
      extensions: <ThemeExtension<dynamic>>[
        colors,
        textStyles,
      ],
    );
  }
}

// ----------------------------------------------------------------------------
// Helpers internes
// ----------------------------------------------------------------------------

Color _blend(Color base, Color tint, double amount) =>
    Color.lerp(base, tint, amount)!;

Color _withAlpha(Color c, double alpha) =>
    c.withValues(alpha: alpha.clamp(0.0, 1.0));
