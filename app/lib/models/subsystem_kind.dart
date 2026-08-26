/// Identifiant stable d'un sous-système dans l'état agrégé.
enum SubsystemKind {
  mount,
  tracking,
  network,
  system,
  alignment;

  static SubsystemKind fromJson(String v) => values.firstWhere(
        (k) => k.name == v,
        orElse: () => throw FormatException('SubsystemKind inconnu: $v'),
      );
}
