import '../../services/api_service.dart';
import 'catalogue_models.dart';

/// Façade REST sur `/catalog/objects` + `/goto` (+ `/stop` pour l'abort).
class CatalogueRepository {
  CatalogueRepository({required this.api});

  final ApiService api;

  /// GET /catalog/objects avec filtres optionnels. On charge large (limit 500)
  /// — le catalogue actuel est petit, pagination différée (Macro 4).
  Future<List<CatalogObjectDto>> listObjects({
    String? search,
    double? maxMag,
    bool visibleNow = false,
  }) async {
    final params = <String, String>{'limit': '500'};
    if (search != null && search.isNotEmpty) params['search'] = search;
    if (maxMag != null) params['max_mag'] = maxMag.toString();
    if (visibleNow) params['visible_now'] = 'true';
    final query = params.entries.map((e) => '${e.key}=${e.value}').join('&');
    final j = await api.getJson('/catalog/objects?$query');
    return (j['objects'] as List)
        .map((e) => CatalogObjectDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// POST /goto — pointe la monture sur les coordonnées de l'objet.
  Future<void> goto(double raDeg, double decDeg, String? targetName) async {
    await api.postJson('/goto', {
      'ra_deg': raDeg,
      'dec_deg': decDeg,
      'target_name': targetName,
    });
  }

  /// Abort : réutilise le POST /stop existant (TELESCOPE_ABORT_MOTION).
  Future<void> abort() => api.stop();
}
