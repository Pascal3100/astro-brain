import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../models/overall_status.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';
import 'network_bloc.dart';
import 'network_event.dart';
import 'network_state.dart';

class NetworkScreen extends StatelessWidget {
  const NetworkScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider<NetworkBloc>(
      create: (_) => NetworkBloc(prefs: context.read<SharedPreferences>())
        ..add(const NetworkLoaded()),
      child: const _NetworkView(),
    );
  }
}

class _NetworkView extends StatelessWidget {
  const _NetworkView();

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;

    return BlocListener<NetworkBloc, NetworkState>(
      listenWhen: (prev, curr) =>
          (prev.savedHost != curr.savedHost || prev.savedPort != curr.savedPort) &&
          curr.savedHost != null,
      listener: (ctx, state) {
        ScaffoldMessenger.of(ctx).showSnackBar(
          const SnackBar(
            content: Text("Redémarrer l'app pour appliquer le nouvel hôte"),
          ),
        );
      },
      child: Scaffold(
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
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(DesignTokens.spaceLG),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'RÉSEAU',
                          style: context.textStyles.hudLabel.copyWith(
                            color: colors.accent,
                            letterSpacing: 2.0,
                          ),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _InputPanel(),
                        const SizedBox(height: DesignTokens.spaceMD),
                        const _StatusRow(),
                        const SizedBox(height: DesignTokens.spaceLG),
                        const _ActionButtons(),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _InputPanel extends StatefulWidget {
  const _InputPanel();

  @override
  State<_InputPanel> createState() => _InputPanelState();
}

class _InputPanelState extends State<_InputPanel> {
  late TextEditingController _hostCtrl;
  late TextEditingController _portCtrl;
  bool _initialised = false;

  @override
  void dispose() {
    _hostCtrl.dispose();
    _portCtrl.dispose();
    super.dispose();
  }

  void _maybeInit(NetworkState state) {
    if (_initialised) return;
    _hostCtrl = TextEditingController(text: state.hostInput);
    _portCtrl = TextEditingController(text: state.portInput.toString());
    _initialised = true;
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocConsumer<NetworkBloc, NetworkState>(
      listenWhen: (prev, curr) =>
          prev.savedHost != curr.savedHost &&
          curr.savedHost == null,
      listener: (ctx, state) {
        _hostCtrl.text = state.hostInput;
        _portCtrl.text = state.portInput.toString();
      },
      builder: (ctx, state) {
        _maybeInit(state);

        final inputDecoration = InputDecoration(
          filled: true,
          fillColor: colors.bgGradientTop.withValues(alpha: 0.6),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
            borderSide: BorderSide(
              color: colors.accent.withValues(alpha: 0.3),
            ),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
            borderSide: BorderSide(
              color: colors.accent.withValues(alpha: 0.3),
            ),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
            borderSide: BorderSide(
              color: colors.accent,
              width: DesignTokens.strokeRegular,
            ),
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: DesignTokens.spaceMD,
            vertical: DesignTokens.spaceSM,
          ),
        );

        return HudPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('HÔTE', style: text.hudCaption.copyWith(color: colors.textMuted)),
              const SizedBox(height: DesignTokens.spaceSM),
              TextField(
                controller: _hostCtrl,
                style: text.hudValue.copyWith(color: colors.textPrimary),
                decoration: inputDecoration,
                keyboardType: TextInputType.url,
                autocorrect: false,
                onChanged: (v) =>
                    ctx.read<NetworkBloc>().add(NetworkHostChanged(v)),
              ),
              const SizedBox(height: DesignTokens.spaceMD),
              Text('PORT', style: text.hudCaption.copyWith(color: colors.textMuted)),
              const SizedBox(height: DesignTokens.spaceSM),
              TextField(
                controller: _portCtrl,
                style: text.hudValue.copyWith(color: colors.textPrimary),
                decoration: inputDecoration,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                onChanged: (v) {
                  final port = int.tryParse(v);
                  if (port != null) {
                    ctx.read<NetworkBloc>().add(NetworkPortChanged(port));
                  }
                },
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow();

  @override
  Widget build(BuildContext context) {
    final text = context.textStyles;
    final colors = context.colors;

    return BlocBuilder<NetworkBloc, NetworkState>(
      builder: (ctx, state) {
        final (dotStatus, label) = switch (state.testStatus) {
          TestStatus.idle => (OverallStatus.gray, 'INACTIF'),
          TestStatus.testing => (OverallStatus.blue, 'TEST EN COURS…'),
          TestStatus.ok => (OverallStatus.green, 'CONNEXION OK'),
          TestStatus.error => (
              OverallStatus.red,
              'ERREUR: ${state.testError ?? ''}',
            ),
        };

        return Row(
          children: [
            GlobalDot(status: dotStatus),
            const SizedBox(width: DesignTokens.spaceSM),
            Expanded(
              child: Text(
                label,
                style: text.hudCaption.copyWith(color: colors.textMuted),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ActionButtons extends StatelessWidget {
  const _ActionButtons();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<NetworkBloc, NetworkState>(
      builder: (ctx, state) {
        final isTesting = state.testStatus == TestStatus.testing;
        final canSave = state.dirty && state.testStatus == TestStatus.ok;

        return Wrap(
          spacing: DesignTokens.spaceSM,
          runSpacing: DesignTokens.spaceSM,
          children: [
            FilledButton(
              onPressed: isTesting
                  ? null
                  : () => ctx.read<NetworkBloc>().add(const NetworkTestRequested()),
              child: Text('TESTER', style: context.textStyles.hudBadge),
            ),
            FilledButton(
              onPressed: canSave
                  ? () => ctx.read<NetworkBloc>().add(const NetworkSaveRequested())
                  : null,
              child: Text('ENREGISTRER', style: context.textStyles.hudBadge),
            ),
            OutlinedButton(
              onPressed: () =>
                  ctx.read<NetworkBloc>().add(const NetworkResetRequested()),
              child: Text('RÉINITIALISER', style: context.textStyles.hudBadge),
            ),
          ],
        );
      },
    );
  }
}
