import 'package:flutter/material.dart';

import '../../../features/catalogue/constellations.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../alignment_models.dart';
import '../alignment_repository.dart';
import '../widgets/constellation_chart.dart';

/// Navigateur d'étoiles d'alignement groupées par constellation.
///
/// Charge les étoiles visibles via [repository.fetchVisibleStars()], propose
/// un filtre par constellation (dropdown), liste les étoiles de la constellation
/// sélectionnée, et permet à l'utilisateur d'en choisir une via [onSelected].
///
/// Utilisé comme écran de swap dans le wizard d'alignement 3 étoiles.
class StarNavigatorScreen extends StatefulWidget {
  const StarNavigatorScreen({
    super.key,
    required this.repository,
    required this.onSelected,
  });

  final AlignmentRepository repository;
  final ValueChanged<StarDto> onSelected;

  @override
  State<StarNavigatorScreen> createState() => _StarNavigatorScreenState();
}

class _StarNavigatorScreenState extends State<StarNavigatorScreen> {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  /// `null` = chargement en cours.
  Map<String, List<StarDto>>? _starsByConstellation;
  String? _errorMessage;

  /// Abréviation IAU de la constellation sélectionnée dans le dropdown.
  String? _selectedAbbr;

  /// Étoile actuellement sélectionnée (tap → charge le schéma inline).
  StarDto? _selectedStar;

  /// Schéma de la constellation de l'étoile sélectionnée.
  ConstellationFigureDto? _figure;

  bool _loadingChart = false;

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await widget.repository.fetchVisibleStars();
      if (!mounted) return;
      // Trier les constellations par nom complet français.
      final sorted = Map.fromEntries(
        data.entries.toList()
          ..sort((a, b) {
            final na = constellationFullName(a.key) ?? a.key;
            final nb = constellationFullName(b.key) ?? b.key;
            return na.compareTo(nb);
          }),
      );
      setState(() {
        _starsByConstellation = sorted;
        _selectedAbbr = sorted.keys.firstOrNull;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = e.toString());
    }
  }

  // ---------------------------------------------------------------------------
  // Constellation chart (inline)
  // ---------------------------------------------------------------------------

  Future<void> _selectStar(StarDto star) async {
    final abbr = _selectedAbbr;
    if (abbr == null) return;

    setState(() {
      _loadingChart = true;
      _selectedStar = star;
      _figure = null;
    });
    try {
      final figure = await widget.repository.fetchConstellation(
        abbr,
        raDeg: star.raDeg,
        decDeg: star.decDeg,
      );
      if (!mounted) return;
      setState(() => _figure = figure);
    } on Exception {
      if (!mounted) return;
      setState(() => _selectedStar = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Schéma indisponible pour cette constellation'),
        ),
      );
    } finally {
      if (mounted) setState(() => _loadingChart = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

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
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AstroAppBar(current: AstroScreen.alignment),
                const SizedBox(height: DesignTokens.spaceXL),
                Text(
                  '// CHOISIR UNE ÉTOILE',
                  style: text.hudCaption.copyWith(
                    fontSize: 10,
                    color: colors.textMuted,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(
                  'NAVIGATEUR',
                  style: text.hudValue.copyWith(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 2.0,
                    color: colors.textPrimary,
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                if (_errorMessage != null)
                  _ErrorView(message: _errorMessage!, onRetry: _load)
                else if (_starsByConstellation == null)
                  const Expanded(
                    child: Center(child: CircularProgressIndicator()),
                  )
                else ...[
                  _ConstellationDropdown(
                    value: _selectedAbbr,
                    abbrs: _starsByConstellation!.keys.toList(),
                    onChanged: (abbr) => setState(() {
                      _selectedAbbr = abbr;
                      _selectedStar = null;
                      _figure = null;
                    }),
                  ),
                  const SizedBox(height: DesignTokens.spaceLG),
                  if (_selectedStar == null) ...[
                    // ---- Liste d'étoiles ----
                    Expanded(
                      child: _StarList(
                        stars:
                            _starsByConstellation![_selectedAbbr] ?? const [],
                        loadingChart: _loadingChart,
                        onTapStar: _selectStar,
                      ),
                    ),
                  ] else ...[
                    // ---- Schéma inline + bouton choisir ----
                    if (_figure != null)
                      ConstellationChart(figure: _figure!)
                    else
                      const Center(child: CircularProgressIndicator()),
                    const SizedBox(height: DesignTokens.spaceLG),
                    _ChooseButton(
                      onTap: () => widget.onSelected(_selectedStar!),
                    ),
                    const SizedBox(height: DesignTokens.spaceSM),
                    TextButton(
                      onPressed: () => setState(() {
                        _selectedStar = null;
                        _figure = null;
                      }),
                      child: const Text('← Retour à la liste'),
                    ),
                  ],
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _ConstellationDropdown
// ---------------------------------------------------------------------------

class _ConstellationDropdown extends StatelessWidget {
  const _ConstellationDropdown({
    required this.value,
    required this.abbrs,
    required this.onChanged,
  });

  final String? value;
  final List<String> abbrs;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientTop.withValues(alpha: 0.5),
        border:
            Border.all(color: colors.accent.withValues(alpha: 0.22)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isExpanded: true,
          dropdownColor: colors.bgGradientBottom,
          iconEnabledColor: colors.accent,
          style: text.hudValue.copyWith(color: colors.textPrimary),
          items: abbrs
              .map(
                (abbr) => DropdownMenuItem<String>(
                  value: abbr,
                  child: Text(constellationFullName(abbr) ?? abbr),
                ),
              )
              .toList(),
          onChanged: onChanged,
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _StarList
// ---------------------------------------------------------------------------

class _StarList extends StatelessWidget {
  const _StarList({
    required this.stars,
    required this.loadingChart,
    required this.onTapStar,
  });

  final List<StarDto> stars;
  final bool loadingChart;
  final ValueChanged<StarDto> onTapStar;

  @override
  Widget build(BuildContext context) {
    if (stars.isEmpty) {
      return Center(
        child: Text(
          'Aucune étoile visible',
          style: TextStyle(color: context.colors.textMuted),
        ),
      );
    }
    return ListView.separated(
      itemCount: stars.length,
      separatorBuilder: (_, _) =>
          const SizedBox(height: DesignTokens.spaceSM),
      itemBuilder: (_, i) => _StarTile(
        star: stars[i],
        loading: loadingChart,
        onTap: () => onTapStar(stars[i]),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _StarTile
// ---------------------------------------------------------------------------

class _StarTile extends StatelessWidget {
  const _StarTile({
    required this.star,
    required this.loading,
    required this.onTap,
  });

  final StarDto star;
  final bool loading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return InkWell(
      onTap: loading ? null : onTap,
      borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: DesignTokens.spaceMD,
          vertical: DesignTokens.spaceSM,
        ),
        decoration: BoxDecoration(
          color: colors.bgGradientTop.withValues(alpha: 0.6),
          border: Border.all(
            color: colors.accent.withValues(alpha: 0.15),
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    star.name,
                    style: text.hudValue.copyWith(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: colors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: DesignTokens.spaceXXS),
                  Text(
                    '${star.bayer} · mag ${star.mag.toStringAsFixed(2)}',
                    style: TextStyle(
                      fontSize: 11,
                      color: colors.textMuted,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: colors.accent.withValues(alpha: 0.6),
              size: DesignTokens.iconSizeMD,
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _ChooseButton
// ---------------------------------------------------------------------------

class _ChooseButton extends StatelessWidget {
  const _ChooseButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(DesignTokens.spaceLG),
        decoration: BoxDecoration(
          color: colors.accent,
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Text(
          'CHOISIR CETTE ÉTOILE',
          textAlign: TextAlign.center,
          style: text.hudCaption.copyWith(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
            color: colors.bgGradientTop,
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _ErrorView
// ---------------------------------------------------------------------------

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Expanded(
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              message,
              style: TextStyle(color: colors.dotError),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: DesignTokens.spaceMD),
            OutlinedButton(
              onPressed: onRetry,
              child: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }
}
