/// Traduit les messages d'erreur techniques renvoyés par le backend pour
/// le sous-système `mount` en libellés lisibles par un opérateur.
///
/// Les messages bruts (errno, traces de port série, etc.) restent dans les
/// logs `journalctl` du Pi pour le diagnostic ; cette fonction sert juste à
/// masquer ce qui n'a pas de sens pour l'utilisateur final dans l'UI.
String? humanizeMountMessage(String? raw) {
  if (raw == null || raw.isEmpty) return raw;
  final lower = raw.toLowerCase();

  // Port série introuvable : la monture n'est tout simplement pas branchée
  // (ou pas reconnue) côté Pi.
  if (lower.contains('/dev/tty') &&
      (lower.contains('no such file') ||
          lower.contains('errno 2') ||
          lower.contains('could not open port'))) {
    return 'Monture non détectée — vérifie le câble USB.';
  }

  // Port présent mais accès refusé (souvent un souci de groupe `dialout`).
  if (lower.contains('permission denied') && lower.contains('/dev/tty')) {
    return 'Accès refusé au port série de la monture.';
  }

  // Timeout côté nexstarpy (la monture est branchée mais ne répond pas).
  if (lower.contains('timeout') || lower.contains('timed out')) {
    return 'Pas de réponse de la monture — réessaye le branchement.';
  }

  // Pattern non reconnu : on garde le message brut, pas de mensonge.
  return raw;
}
