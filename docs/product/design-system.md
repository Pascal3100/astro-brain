# Design system

Style visuel et conventions UI de l'app Flutter.

## Style général

- **Material Design 3**, esthétique HUD spatial.
- **Deux thèmes** : jour (bleu spatial) et nuit (rouge astro). Les deux sont sur fond sombre — le toggle ne change que la teinte d'accent.
  - **Jour** : accent `#60A0FF`, text `#B4D7FF`, gradient bg `#060A18 → #0A0818`
  - **Nuit** : accent `#FF5A3A`, text `#FFAA9B`, gradient bg `#0C0606 → #0A0606` (aucun bleu ni vert pour préserver la vision nocturne)
- **Typographie** : Inter (texte courant), JetBrains Mono (libellés HUD : labels, valeurs, badges).
- **Iconographie** : Phosphor Icons (`phosphor_flutter`).

## Tokens

Source de vérité : `app/lib/theme/design_tokens.dart`.

Trois couches :
1. **`DesignTokens`** — constantes brutes (Color, double, Duration). Aucun `Color(0xFF...)` en dehors de ce fichier.
2. **`AppColors`** (ThemeExtension) — slots sémantiques que M3 n'a pas : `accent`, `accentGlow`, `bgGradientTop/Bottom`, `grid`, `textPrimary/Muted`, `dotOk/Transition/Warn/Error`. Deux instances `const` : `AppColors.day`, `AppColors.night`. Accès via `context.colors`.
3. **`AppTextStyles`** (ThemeExtension) — styles HUD monospace : `hudLabel`, `hudValue`, `hudCaption`, `hudBadge`. Inter pour le `TextTheme` M3 standard. Accès via `context.textStyles`.

Pas de `GoogleFonts.inter(...)` hors `app_typography.dart`.

## AppBar partagée

Convention : tous les écrans (Hub, Manuel, GoTo, Status, Setup, wizard d'alignement…) affichent une **AppBar template** persistante.

Contenu minimum :
- Pastille `overall` + libellé court (`SYSTEM OK`, `NOT ALIGNED`, `OFFLINE`…) — tap → écran Status.
- Toggle thème jour/nuit (icône soleil/lune).
- Bouton reconnect conditionnel quand `connection == offline`.

Source de vérité actuelle : `app/lib/features/home/widgets/status_bar.dart` (`StatusBar`). À factoriser en widget partagé `AstroAppBar` quand on introduira le Hub (v0.2/v0.3).

Les écrans qui ont besoin d'un titre de page le posent **en dessous** de l'AppBar partagée, pas à sa place.

## Espacement

Échelle base 4 : `spaceXXS=2, spaceXS=4, spaceSM=8, spaceMD=12, spaceLG=16, spaceXL=24, space2XL=32, space3XL=48, space4XL=64`.

## Rayons

`radiusSM=4, radiusMD=8, radiusLG=12, radiusXL=16, radiusPill=999`. Les bords HUD sont volontairement **angulaires** — `radiusPill` est l'exception (pastilles, switches).

## Animations

- `motionFast = 120ms` — tap feedback (D-Pad press, toggle).
- `motionMedium = 240ms` — transitions d'écran courtes.
- `motionSlow = 400ms` — transitions plus marquées.
- `motionHalo = 1600ms` — halo splash, pulsations long-press.

## États globaux (`overall`)

5 valeurs utilisées dans toute l'UI :
- `green` — tout OK
- `blue` — transition (acquisition, mouvement, wizard en cours…)
- `orange` — degraded (capteur manquant, calibration, network offline)
- `red` — fatal (monture en erreur, hardware failure)
- `offline` — pas de connexion au Pi

Voir `widgets/global_dot.dart` pour le rendu pastille + glow.

## Pattern d'accès dans le code

```dart
final colors = context.colors;          // AppColors (ThemeExtension)
final text = context.textStyles;        // AppTextStyles (ThemeExtension)
DesignTokens.spaceLG;                   // constante brute
```
