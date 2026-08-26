import '../../../services/api_service.dart';

/// Site d'observation persisté côté Pi (`observing_site`).
///
/// Depuis le retrait du module DroTek (ADR 2026-08-26), c'est l'unique
/// source de position du backend : plus de fix GPS local sur le Pi.
class ObservingSite {
  const ObservingSite({
    required this.lat,
    required this.lon,
    required this.setAt,
  });

  factory ObservingSite.fromJson(Map<String, dynamic> json) => ObservingSite(
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
        setAt: DateTime.parse(json['set_at'] as String),
      );

  final double lat;
  final double lon;
  final DateTime setAt;
}

/// Façade REST sur le router `/site` du backend.
class SiteRepository {
  SiteRepository({required this.api});

  final ApiService api;

  /// GET /site — `null` si aucun site n'a jamais été réglé.
  ///
  /// L'absence de site est un état nominal : le backend répond 200 + `null`,
  /// pas 404.
  Future<ObservingSite?> getSite() async {
    final json = await api.getJsonOrNull('/site');
    if (json == null) return null;
    return ObservingSite.fromJson(json);
  }

  /// PUT /site — écrit le site d'observation (204 No Content).
  ///
  /// Écriture sur action explicite uniquement : une écriture automatique
  /// depuis un GPS téléphone qui gigue invaliderait un alignement valide
  /// (garde ΔGPS 20 m côté backend).
  Future<void> putSite(double lat, double lon) =>
      api.putJson('/site', {'lat': lat, 'lon': lon});
}
