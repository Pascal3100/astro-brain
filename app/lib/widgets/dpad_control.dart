import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

/// Direction émise par [DPadControl] lors d'une pression.
enum DPadDirection { up, down, left, right }

/// Widget présentationnel en croix directionnelle (D-Pad).
///
/// Aucune dépendance BLoC — les interactions remontent via [onPress] et
/// [onRelease]. Le caller détermine comment mapper les directions vers des
/// commandes métier.
///
/// Chaque bouton expose une [Key] testable : `'dpad-up'`, `'dpad-down'`,
/// `'dpad-left'`, `'dpad-right'`.
class DPadControl extends StatelessWidget {
  const DPadControl({
    super.key,
    required this.onPress,
    required this.onRelease,
    this.cellSize,
    this.iconSize,
    this.spacing = DesignTokens.spaceMD,
  });

  /// Appelé dès le premier contact sur un bouton avec la direction pressée.
  final ValueChanged<DPadDirection> onPress;

  /// Appelé quand le doigt quitte le bouton (up ou cancel).
  final VoidCallback onRelease;

  /// Taille fixe de chaque cellule de la grille 3×3 (optionnel).
  final double? cellSize;

  /// Taille de l'icône dans chaque bouton (optionnel — défaut : iconSizeXL).
  final double? iconSize;

  /// Espacement entre les cellules (défaut : [DesignTokens.spaceMD]).
  final double spacing;

  @override
  Widget build(BuildContext context) {
    final effectiveIconSize = iconSize ?? DesignTokens.iconSizeXL;
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      mainAxisSpacing: spacing,
      crossAxisSpacing: spacing,
      children: [
        const SizedBox(),
        _Btn(
          key: const Key('dpad-up'),
          icon: PhosphorIconsBold.caretUp,
          direction: DPadDirection.up,
          iconSize: effectiveIconSize,
          onPress: onPress,
          onRelease: onRelease,
        ),
        const SizedBox(),
        _Btn(
          key: const Key('dpad-left'),
          icon: PhosphorIconsBold.caretLeft,
          direction: DPadDirection.left,
          iconSize: effectiveIconSize,
          onPress: onPress,
          onRelease: onRelease,
        ),
        const SizedBox(),
        _Btn(
          key: const Key('dpad-right'),
          icon: PhosphorIconsBold.caretRight,
          direction: DPadDirection.right,
          iconSize: effectiveIconSize,
          onPress: onPress,
          onRelease: onRelease,
        ),
        const SizedBox(),
        _Btn(
          key: const Key('dpad-down'),
          icon: PhosphorIconsBold.caretDown,
          direction: DPadDirection.down,
          iconSize: effectiveIconSize,
          onPress: onPress,
          onRelease: onRelease,
        ),
        const SizedBox(),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Bouton individuel du D-Pad
// ---------------------------------------------------------------------------

class _Btn extends StatefulWidget {
  const _Btn({
    super.key,
    required this.icon,
    required this.direction,
    required this.iconSize,
    required this.onPress,
    required this.onRelease,
  });

  final IconData icon;
  final DPadDirection direction;
  final double iconSize;
  final ValueChanged<DPadDirection> onPress;
  final VoidCallback onRelease;

  @override
  State<_Btn> createState() => _BtnState();
}

class _BtnState extends State<_Btn> {
  bool _pressed = false;

  void _handlePointerDown(PointerDownEvent event) {
    setState(() => _pressed = true);
    widget.onPress(widget.direction);
  }

  void _handlePointerUp(PointerUpEvent event) {
    if (!_pressed) return;
    setState(() => _pressed = false);
    widget.onRelease();
  }

  void _handlePointerCancel(PointerCancelEvent event) {
    if (!_pressed) return;
    setState(() => _pressed = false);
    widget.onRelease();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Listener(
      onPointerDown: _handlePointerDown,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerCancel,
      child: AnimatedContainer(
        duration: DesignTokens.motionFast,
        curve: Curves.easeOut,
        decoration: BoxDecoration(
          color: Color.lerp(
            colors.bgGradientTop,
            colors.accent,
            _pressed ? 0.32 : 0.08,
          ),
          border: Border.all(
            color: colors.accent.withValues(alpha: _pressed ? 1 : 0.4),
            width:
                _pressed ? DesignTokens.strokeBold : DesignTokens.strokeRegular,
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          boxShadow: _pressed
              ? [
                  BoxShadow(
                    color: colors.accentGlow,
                    blurRadius: 16,
                    spreadRadius: 1,
                  ),
                ]
              : null,
        ),
        child: Center(
          child: PhosphorIcon(
            widget.icon,
            color: colors.accent,
            size: widget.iconSize,
          ),
        ),
      ),
    );
  }
}
