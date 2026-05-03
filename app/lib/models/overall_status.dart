/// Statut global agrégé (spec v0.1 : règles 1→4 dans `overall`).
/// `offline` et `gray` sont des états CÔTÉ APP (Pi injoignable, neutre/désactivé),
/// pas émis par le backend.
enum OverallStatus {
  green,
  blue,
  orange,
  red,
  offline,
  gray;

  static OverallStatus fromJson(String v) => switch (v) {
        'green' => OverallStatus.green,
        'blue' => OverallStatus.blue,
        'orange' => OverallStatus.orange,
        'red' => OverallStatus.red,
        _ => throw FormatException('OverallStatus inconnu: $v'),
      };
}
