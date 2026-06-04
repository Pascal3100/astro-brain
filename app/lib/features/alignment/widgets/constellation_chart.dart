import 'package:flutter/material.dart';

import '../alignment_models.dart';
import '../../../theme/design_tokens.dart';

/// Schéma au trait d'une constellation, étoile cible mise en évidence.
///
/// Orienté comme le ciel (haut = zénith) si [figure.oriented] est `true`,
/// sinon projection atlas (RA/Dec).
/// Les couleurs proviennent du [Theme] actif (jour bleu / nuit rouge).
class ConstellationChart extends StatelessWidget {
  const ConstellationChart({super.key, required this.figure});

  final ConstellationFigureDto figure;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    // Nœud cible — `null` si aucun nœud n'est marqué isTarget.
    final ConstellationNodeDto? target = figure.nodes.cast<ConstellationNodeDto?>().firstWhere(
      (n) => n!.isTarget,
      orElse: () => null,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        // ---- En-tête : nom de la constellation + indicateur d'orientation ----
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(figure.name, style: textTheme.labelLarge),
            if (figure.oriented)
              Text(
                'N↑ orienté ciel',
                style: textTheme.labelSmall?.copyWith(color: scheme.tertiary),
              ),
          ],
        ),

        const SizedBox(height: DesignTokens.spaceSM),

        // ---- Canvas du schéma ----
        AspectRatio(
          aspectRatio: 16 / 10,
          child: CustomPaint(
            painter: _ChartPainter(
              figure: figure,
              starColor: scheme.onSurface,
              lineColor: scheme.outline,
              targetColor: scheme.primary,
            ),
            child: const SizedBox.expand(),
          ),
        ),

        // ---- Légende cible (real Text widget for testability) ----
        if (target != null) ...[
          const SizedBox(height: DesignTokens.spaceXS),
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: scheme.primary,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: DesignTokens.spaceXS),
              Text(
                target.label,
                style: textTheme.labelSmall?.copyWith(color: scheme.primary),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Painter interne
// ---------------------------------------------------------------------------

class _ChartPainter extends CustomPainter {
  const _ChartPainter({
    required this.figure,
    required this.starColor,
    required this.lineColor,
    required this.targetColor,
  });

  final ConstellationFigureDto figure;
  final Color starColor;
  final Color lineColor;
  final Color targetColor;

  /// Coordonnées brutes (avant normalisation) : Az/Alt si orienté, -RA/Dec sinon.
  List<Offset> _rawPoints() => figure.nodes.map((n) {
        if (figure.oriented && n.az != null && n.alt != null) {
          return Offset(n.az!, n.alt!);
        }
        // Atlas : RA croît vers la droite en degrés négatifs pour respecter
        // la convention Est-Ouest du ciel.
        return Offset(-n.raDeg, n.decDeg);
      }).toList();

  @override
  void paint(Canvas canvas, Size size) {
    final pts = _rawPoints();
    if (pts.isEmpty) return;

    // ---- Normalisation → coordonnées écran ----
    const margin = 24.0;

    final xs = pts.map((p) => p.dx);
    final ys = pts.map((p) => p.dy);
    final minX = xs.reduce((a, b) => a < b ? a : b);
    final maxX = xs.reduce((a, b) => a > b ? a : b);
    final minY = ys.reduce((a, b) => a < b ? a : b);
    final maxY = ys.reduce((a, b) => a > b ? a : b);

    double sx(double x) => (maxX == minX)
        ? size.width / 2
        : margin + (x - minX) / (maxX - minX) * (size.width - 2 * margin);

    // Y inversé : altitude haute → haut de l'écran.
    double sy(double y) => (maxY == minY)
        ? size.height / 2
        : size.height -
            (margin + (y - minY) / (maxY - minY) * (size.height - 2 * margin));

    final screen =
        pts.map((p) => Offset(sx(p.dx), sy(p.dy))).toList(growable: false);

    // ---- Segments ----
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = DesignTokens.strokeRegular
      ..style = PaintingStyle.stroke;

    for (final seg in figure.segments) {
      canvas.drawLine(screen[seg[0]], screen[seg[1]], linePaint);
    }

    // ---- Nœuds ----
    for (var i = 0; i < figure.nodes.length; i++) {
      final n = figure.nodes[i];
      final pt = screen[i];

      if (n.isTarget) {
        // Halo translucide + point accentué
        canvas.drawCircle(
          pt,
          11,
          Paint()..color = targetColor.withValues(alpha: 0.20),
        );
        canvas.drawCircle(pt, 4.5, Paint()..color = targetColor);
      } else {
        // Rayon proportionnel à la magnitude (étoiles brillantes = plus grand)
        final r = (4.0 - n.mag * 0.6).clamp(1.5, 4.0);
        canvas.drawCircle(pt, r, Paint()..color = starColor);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) => old.figure != figure;
}
