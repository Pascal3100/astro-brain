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
import 'widgets/catalogue_detail_sheet.dart';
import 'widgets/catalogue_object_card.dart';

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
          child: Column(
            children: const [
              AstroAppBar(current: AstroScreen.catalogue),
              _NotAlignedBanner(),
              _Filters(),
              Expanded(child: _ObjectList()),
            ],
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
              hintText: 'Rechercher une étoile…',
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
              return Wrap(
                spacing: DesignTokens.spaceSM,
                children: [
                  FilterChip(
                    label: const Text('VISIBLE MAINTENANT'),
                    selected: filters.visibleNow && gpsFixed,
                    onSelected: gpsFixed
                        ? (v) =>
                            ctx.read<CatalogueBloc>().add(VisibleNowToggled(v))
                        : null,
                  ),
                  FilterChip(
                    label: const Text('MAG ≤ 3'),
                    selected: filters.maxMag == 3.0,
                    onSelected: (v) => ctx
                        .read<CatalogueBloc>()
                        .add(MagFilterChanged(v ? 3.0 : null)),
                  ),
                  FilterChip(
                    label: const Text('MAG ≤ 2'),
                    selected: filters.maxMag == 2.0,
                    onSelected: (v) => ctx
                        .read<CatalogueBloc>()
                        .add(MagFilterChanged(v ? 2.0 : null)),
                  ),
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
        onGoto: () => bloc.add(
          GoToRequested(obj.raDeg, obj.decDeg, obj.name),
        ),
      ),
    );
  }
}
