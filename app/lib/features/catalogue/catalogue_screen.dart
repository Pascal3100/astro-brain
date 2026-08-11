import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import '../../widgets/astro_app_bar.dart';
import '../alignment/alignment_wizard_screen.dart';
import 'catalogue_bloc.dart';
import 'catalogue_event.dart';
import 'catalogue_models.dart';
import 'catalogue_state.dart';
import 'constellations.dart';
import 'widgets/catalogue_detail_sheet.dart';
import 'widgets/catalogue_object_card.dart';
import 'widgets/goto_slew_bar.dart';
import 'widgets/reference_banner.dart';
import 'widgets/solar_warning_dialog.dart';

/// Libellés FR des familles d'objets, pour le sélecteur de filtre `kind`.
const Map<String, String> kCatalogKinds = {
  'planet': 'Planètes',
  'moon': 'Lune',
  'sun': 'Soleil',
  'comet': 'Comètes',
  'dso': 'Ciel profond',
  'star': 'Étoiles',
};

/// Page Catalogue — Macro 3 #5. Liste cherchable/filtrable d'objets célestes
/// avec GoTo conditionné à l'alignement.
///
/// Dispatch [CatalogueOpened] dès [initState] pour déclencher le chargement
/// initial sans dépendre du provider parent (F10).
class CatalogueScreen extends StatefulWidget {
  const CatalogueScreen({super.key});

  @override
  State<CatalogueScreen> createState() => _CatalogueScreenState();
}

class _CatalogueScreenState extends State<CatalogueScreen> {
  @override
  void initState() {
    super.initState();
    context.read<CatalogueBloc>().add(const CatalogueOpened());
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
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
          child: BlocListener<CatalogueBloc, CatalogueState>(
            listenWhen: (p, c) =>
                c is CatalogueLoaded && c.gotoOutcome != null,
            listener: (ctx, state) async {
              final outcome = (state as CatalogueLoaded).gotoOutcome;
              switch (outcome) {
                case GotoError(:final message):
                  ScaffoldMessenger.of(ctx)
                      .showSnackBar(SnackBar(content: Text(message)));
                case GotoSolarAck(:final objectId):
                  final confirmed = await showSolarWarningDialog(ctx);
                  if (confirmed && ctx.mounted) {
                    ctx.read<CatalogueBloc>().add(
                        GoToRequested(objectId, confirmSolar: true));
                  }
                case null:
                  break;
              }
            },
            child: Column(
              children: const [
                AstroAppBar(current: AstroScreen.catalogue),
                ReferenceBanner(),
                _NotAlignedBanner(),
                _Filters(),
                Expanded(child: _ObjectList()),
                _SlewBarSlot(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NotAlignedBanner extends StatelessWidget {
  const _NotAlignedBanner();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.system?.isAligned != b.system?.isAligned,
      builder: (ctx, state) {
        if (state.system?.isAligned == true) return const SizedBox.shrink();
        return Container(
          margin: const EdgeInsets.all(DesignTokens.spaceMD),
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotWarn.withValues(alpha: 0.1),
            border: Border.all(color: colors.dotWarn.withValues(alpha: 0.4)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Monture non alignée — pointage indisponible.',
                  style: text.hudCaption.copyWith(color: colors.dotWarn),
                ),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).push(
                  MaterialPageRoute(
                    builder: (_) => const AlignmentWizardScreen(),
                  ),
                ),
                child: const Text('ALIGNER →'),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Filters extends StatefulWidget {
  const _Filters();

  @override
  State<_Filters> createState() => _FiltersState();
}

class _FiltersState extends State<_Filters> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final gpsFixed = context.select<AppBloc, bool>((b) {
      final g = b.state.system?.gps.state.name;
      return g == 'fix2d' || g == 'fix3d';
    });
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: DesignTokens.spaceMD),
      child: Column(
        children: [
          TextField(
            controller: _searchController,
            onChanged: (v) =>
                context.read<CatalogueBloc>().add(SearchChanged(v)),
            style: TextStyle(color: colors.textPrimary),
            decoration: const InputDecoration(
              hintText: 'Rechercher un objet…',
              prefixIcon: Icon(Icons.search),
            ),
          ),
          const SizedBox(height: DesignTokens.spaceSM),
          BlocBuilder<CatalogueBloc, CatalogueState>(
            builder: (ctx, state) {
              final filters = switch (state) {
                CatalogueLoading(:final filters) => filters,
                CatalogueLoaded(:final filters) => filters,
                CatalogueError(:final filters) => filters,
              };
              final available = state is CatalogueLoaded
                  ? state.availableConstellations
                  : const <String>[];
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Wrap(
                    spacing: DesignTokens.spaceSM,
                    children: [
                      FilterChip(
                        label: const Text('VISIBLE MAINTENANT'),
                        selected: filters.visibleNow && gpsFixed,
                        onSelected: gpsFixed
                            ? (v) => ctx
                                .read<CatalogueBloc>()
                                .add(VisibleNowToggled(v))
                            : null,
                      ),
                    ],
                  ),
                  const SizedBox(height: DesignTokens.spaceSM),
                  _MagRangeSlider(
                    minMag: filters.minMag,
                    maxMag: filters.maxMag,
                  ),
                  if (available.isNotEmpty) ...[
                    const SizedBox(height: DesignTokens.spaceSM),
                    _ConstellationDropdown(
                      value: filters.constellation,
                      available: available,
                    ),
                  ],
                  const SizedBox(height: DesignTokens.spaceSM),
                  _KindDropdown(value: filters.kind),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _ObjectList extends StatelessWidget {
  const _ObjectList();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CatalogueBloc, CatalogueState>(
      builder: (ctx, state) {
        return switch (state) {
          CatalogueLoading() =>
            const Center(child: CircularProgressIndicator()),
          CatalogueError(:final message) => Center(child: Text(message)),
          CatalogueLoaded(:final objects) => ListView.separated(
              padding: const EdgeInsets.all(DesignTokens.spaceMD),
              itemCount: objects.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: DesignTokens.spaceSM),
              itemBuilder: (c, i) => CatalogueObjectCard(
                object: objects[i],
                onTap: () => _openDetail(ctx, objects[i]),
              ),
            ),
        };
      },
    );
  }

  void _openDetail(BuildContext context, CatalogObjectDto obj) {
    final bloc = context.read<CatalogueBloc>();
    final isAligned = context.read<AppBloc>().state.system?.isAligned == true;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: context.colors.bgGradientBottom,
      isScrollControlled: true,
      builder: (_) => CatalogueDetailSheet(
        object: obj,
        isAligned: isAligned,
        onGoto: () => bloc.add(GoToRequested(obj.qualifiedId)),
      ),
    );
  }
}

class _SlewBarSlot extends StatelessWidget {
  const _SlewBarSlot();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) =>
          a.system?.gotoInProgress != b.system?.gotoInProgress ||
          a.system?.gotoTarget != b.system?.gotoTarget,
      builder: (ctx, state) {
        if (state.system?.gotoInProgress != true) {
          return const SizedBox.shrink();
        }
        final target =
            state.system?.gotoTarget?['target_name'] as String?;
        return GotoSlewBar(
          targetName: target ?? 'cible',
          onStop: () =>
              ctx.read<CatalogueBloc>().add(const AbortRequested()),
        );
      },
    );
  }
}

/// Menu déroulant de filtre par constellation (noms complets). N'affiche que
/// les constellations présentes dans la liste courante ; « Toutes » = pas de
/// filtre. Le filtrage est fait côté app par le [CatalogueBloc].
class _ConstellationDropdown extends StatelessWidget {
  const _ConstellationDropdown({required this.value, required this.available});

  final String? value;
  final List<String> available;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientTop.withValues(alpha: 0.5),
        border: Border.all(color: colors.accent.withValues(alpha: 0.22)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String?>(
          value: value,
          isExpanded: true,
          dropdownColor: colors.bgGradientBottom,
          iconEnabledColor: colors.accent,
          style: text.hudValue.copyWith(color: colors.textPrimary),
          items: [
            DropdownMenuItem<String?>(
              value: null,
              child: Text(
                'Toutes les constellations',
                style: text.hudValue.copyWith(color: colors.textMuted),
              ),
            ),
            ...available.map(
              (abbr) => DropdownMenuItem<String?>(
                value: abbr,
                child: Text(constellationFullName(abbr) ?? abbr),
              ),
            ),
          ],
          onChanged: (v) =>
              context.read<CatalogueBloc>().add(ConstellationChanged(v)),
        ),
      ),
    );
  }
}

/// Menu déroulant de filtre par famille (`kind`) : `null` = toutes les
/// familles. Le filtrage est fait LOCALEMENT (requête SQL sur
/// `reference.sqlite` en cache), pas côté backend.
class _KindDropdown extends StatelessWidget {
  const _KindDropdown({required this.value});
  final String? value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientTop.withValues(alpha: 0.5),
        border: Border.all(color: colors.accent.withValues(alpha: 0.22)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String?>(
          value: value,
          isExpanded: true,
          dropdownColor: colors.bgGradientBottom,
          iconEnabledColor: colors.accent,
          style: text.hudValue.copyWith(color: colors.textPrimary),
          items: [
            DropdownMenuItem<String?>(
              value: null,
              child: Text('Toutes les familles',
                  style: text.hudValue.copyWith(color: colors.textMuted)),
            ),
            ...kCatalogKinds.entries.map(
              (e) => DropdownMenuItem<String?>(
                value: e.key,
                child: Text(e.value),
              ),
            ),
          ],
          onChanged: (v) =>
              context.read<CatalogueBloc>().add(KindFilterChanged(v)),
        ),
      ),
    );
  }
}

/// Bornes du RangeSlider de magnitude : couvre les planètes brillantes
/// (Vénus ≈ −4,6) jusqu'aux Messier faibles (≈ 11). Pas de 1 → 17 crans.
const double _kMagMin = -5;
const double _kMagMax = 12;

/// Filtre de magnitude à double poignée. À bornes pleines = pas de filtre :
/// on émet alors `MagRangeChanged(null, null)` pour lever la plage. Les objets
/// sans magnitude cataloguée restent visibles quoi qu'il arrive (option B,
/// côté providers). Le drag est local ; on ne requête qu'au relâchement.
class _MagRangeSlider extends StatefulWidget {
  const _MagRangeSlider({required this.minMag, required this.maxMag});
  final double? minMag;
  final double? maxMag;

  @override
  State<_MagRangeSlider> createState() => _MagRangeSliderState();
}

class _MagRangeSliderState extends State<_MagRangeSlider> {
  RangeValues? _dragging;

  RangeValues get _values =>
      _dragging ??
      RangeValues(widget.minMag ?? _kMagMin, widget.maxMag ?? _kMagMax);

  bool _isFull(RangeValues v) => v.start <= _kMagMin && v.end >= _kMagMax;

  void _onEnd(RangeValues v) {
    setState(() => _dragging = null);
    context.read<CatalogueBloc>().add(_isFull(v)
        ? const MagRangeChanged(null, null)
        : MagRangeChanged(v.start, v.end));
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final v = _values;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('MAGNITUDE',
                style: text.hudLabel.copyWith(color: colors.textMuted)),
            Text(
              _isFull(v) ? 'toutes' : '${v.start.toInt()} – ${v.end.toInt()}',
              style: text.hudValue.copyWith(color: colors.textPrimary),
            ),
          ],
        ),
        RangeSlider(
          values: v,
          min: _kMagMin,
          max: _kMagMax,
          divisions: (_kMagMax - _kMagMin).toInt(),
          activeColor: colors.accent,
          inactiveColor: colors.accent.withValues(alpha: 0.22),
          labels: RangeLabels('${v.start.toInt()}', '${v.end.toInt()}'),
          onChanged: (nv) => setState(() => _dragging = nv),
          onChangeEnd: _onEnd,
        ),
      ],
    );
  }
}
