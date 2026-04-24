import 'package:flutter/material.dart';

/// Constantes brutes du design system Astro-Brain.
///
/// Ce fichier ne contient que des valeurs primitives (Color, double, Duration).
/// Pour les couleurs sémantiques (accent, glow, dots d'état…), voir [AppColors].
/// Pour les styles de texte, voir [AppTextStyles].
class DesignTokens {
  DesignTokens._();

  // ---------------------------------------------------------------------------
  // Palette jour — « bleu spatial »
  // ---------------------------------------------------------------------------

  static const Color dayBgTop = Color(0xFF060A18);
  static const Color dayBgBottom = Color(0xFF0A0818);
  static const Color dayGrid = Color(0x0A3C82FF); // rgba(60,130,255,0.04)

  static const Color dayText = Color(0xFFB4D7FF); // rgba(180,215,255)
  static const Color dayTextMuted = Color(0x99B4D7FF);

  static const Color dayAccent = Color(0xFF60A0FF);
  static const Color dayAccentGlow = Color(0x993C82FF); // rgba(60,130,255,0.6)

  static const Color dayDotOk = Color(0xFF00E676);
  static const Color dayDotTransition = Color(0xFF40C4FF);
  static const Color dayDotWarn = Color(0xFFFFB300);
  static const Color dayDotError = Color(0xFFFF5252);

  // ---------------------------------------------------------------------------
  // Palette nuit — « rouge astro » (aucun bleu ni vert)
  // ---------------------------------------------------------------------------

  static const Color nightBgTop = Color(0xFF0C0606);
  static const Color nightBgBottom = Color(0xFF0A0606);
  static const Color nightGrid = Color(0x14FF5A3A);

  static const Color nightText = Color(0xFFFFAA9B); // rgba(255,170,155)
  static const Color nightTextMuted = Color(0x99FFAA9B);

  static const Color nightAccent = Color(0xFFFF5A3A);
  static const Color nightAccentGlow = Color(0xB3FF5A3A); // rgba(255,90,58,0.7)

  static const Color nightDotOk = Color(0xFF8B2020);
  static const Color nightDotTransition = Color(0xFFC04040);
  static const Color nightDotWarn = Color(0xFFE04020);
  static const Color nightDotError = Color(0xFFFF3030);

  // ---------------------------------------------------------------------------
  // Échelle d'espacement (base 4)
  // ---------------------------------------------------------------------------

  static const double spaceXXS = 2.0;
  static const double spaceXS = 4.0;
  static const double spaceSM = 8.0;
  static const double spaceMD = 12.0;
  static const double spaceLG = 16.0;
  static const double spaceXL = 24.0;
  static const double space2XL = 32.0;
  static const double space3XL = 48.0;
  static const double space4XL = 64.0;

  // ---------------------------------------------------------------------------
  // Rayons (corners HUD : angles légers, jamais pill sauf exceptions)
  // ---------------------------------------------------------------------------

  static const double radiusSM = 4.0;
  static const double radiusMD = 8.0;
  static const double radiusLG = 12.0;
  static const double radiusXL = 16.0;
  static const double radiusPill = 999.0;

  // ---------------------------------------------------------------------------
  // Épaisseurs de traits (bordures HUD)
  // ---------------------------------------------------------------------------

  static const double strokeThin = 1.0;
  static const double strokeRegular = 1.5;
  static const double strokeBold = 2.0;

  // ---------------------------------------------------------------------------
  // Durations d'animation
  // ---------------------------------------------------------------------------

  static const Duration motionFast = Duration(milliseconds: 120);
  static const Duration motionMedium = Duration(milliseconds: 240);
  static const Duration motionSlow = Duration(milliseconds: 400);
  static const Duration motionHalo = Duration(milliseconds: 1600); // halo splash

  // ---------------------------------------------------------------------------
  // Dimensions fixes UI
  // ---------------------------------------------------------------------------

  static const double statusDotSize = 12.0;
  static const double statusDotSizeLg = 16.0;
  static const double iconSizeSM = 16.0;
  static const double iconSizeMD = 20.0;
  static const double iconSizeLG = 24.0;
  static const double iconSizeXL = 32.0;
}
