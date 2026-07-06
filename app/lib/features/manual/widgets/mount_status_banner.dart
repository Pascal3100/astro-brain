import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../models/subsystem_states.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../manual_bloc.dart';

/// Bannière affichée en mode manuel quand la monture n'est pas pilotable
/// (erreur INDI ou lien déconnecté).
///
/// Sans elle, un slew échoué est invisible : `POST /slew` renvoie 200 même
/// quand l'adaptateur backend échoue, et l'échec ne remonte que par l'état
/// SSE `mount` (`error` / `disconnected`). L'utilisateur appuyait sur le
/// D-Pad sans rien voir ni bouger (journal S38).
class MountStatusBanner extends StatelessWidget {
  const MountStatusBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.system?.mount != b.system?.mount,
      builder: (context, app) {
        final mount = app.system?.mount;
        final blocking = mount != null &&
            (mount.state == MountState.error ||
                mount.state == MountState.disconnected);
        if (!blocking) return const SizedBox.shrink();

        final colors = context.colors;
        final label = mount.state == MountState.disconnected
            ? 'Monture déconnectée'
            : 'Erreur monture';
        final message = mount.message;
        final full = message == null ? label : '$label — $message';

        return Container(
          key: const Key('mount-status-banner'),
          width: double.infinity,
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotError.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(DesignTokens.radiusSM),
            border: Border.all(color: colors.dotError),
          ),
          child: Row(
            children: [
              Icon(Icons.error_outline, color: colors.dotError, size: 18),
              const SizedBox(width: DesignTokens.spaceSM),
              Expanded(
                child: Text(
                  full,
                  style: context.textStyles.hudCaption
                      .copyWith(color: colors.dotError),
                ),
              ),
              const SizedBox(width: DesignTokens.spaceSM),
              TextButton(
                key: const Key('mount-reconnect-button'),
                onPressed: () => context
                    .read<ManualBloc>()
                    .add(const ManualReconnectPressed()),
                style: TextButton.styleFrom(
                  foregroundColor: colors.dotError,
                  padding: const EdgeInsets.symmetric(
                    horizontal: DesignTokens.spaceSM,
                  ),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: const Text('RECONNECTER'),
              ),
            ],
          ),
        );
      },
    );
  }
}
