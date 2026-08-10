import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import 'reference_models.dart';
import 'reference_repository.dart';

/// Détail « Almanach » : fraîcheur + fenêtre couverte + resynchronisation.
class AlmanacScreen extends StatefulWidget {
  const AlmanacScreen({super.key});
  @override
  State<AlmanacScreen> createState() => _AlmanacScreenState();
}

class _AlmanacScreenState extends State<AlmanacScreen> {
  int _refresh = 0;
  bool _syncing = false;

  Future<void> _sync() async {
    setState(() => _syncing = true);
    try {
      final r = await context.read<ReferenceRepository>().sync();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Sync : ${r.status}')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Resynchronisation impossible.')));
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
          _refresh++;
        });
      }
    }
  }

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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const AstroAppBar(current: AstroScreen.setup),
              Padding(
                padding: const EdgeInsets.all(DesignTokens.spaceLG),
                child: FutureBuilder<ReferenceStatusDto>(
                  key: ValueKey(_refresh),
                  future: context.read<ReferenceRepository>().getStatus(),
                  builder: (ctx, snap) {
                    final d = snap.data;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ALMANACH', style: text.hudLabel),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          d == null
                              ? '—'
                              : d.ready
                                  ? 'Prêt · généré le ${d.generatedAt ?? '?'}\n'
                                      'Couvre ${d.windowStart ?? '?'} → ${d.windowEnd ?? '?'}'
                                  : 'Indisponible',
                          style: text.hudValue
                              .copyWith(color: colors.textPrimary),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        FilledButton(
                          onPressed: _syncing ? null : _sync,
                          child: Text(_syncing
                              ? 'RESYNCHRONISATION…'
                              : 'RESYNCHRONISER'),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
