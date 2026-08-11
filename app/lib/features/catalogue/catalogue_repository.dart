import '../../services/api_service.dart';
import 'catalogue_models.dart';
import 'local/catalogue_providers.dart';
import 'local/local_catalogue.dart';
import 'local/visibility.dart';

/// Catalogue lu LOCALEMENT (reference.sqlite en cache) ; GoTo reste online
/// (l'id part au Pi, qui résout contre sa propre copie).
class CatalogueRepository {
  CatalogueRepository({
    required this.api,
    required LocalCatalogue catalogue,
    required Visibility visibility,
  })  : _catalogue = catalogue,
        _visibility = visibility;

  final ApiService api;
  final LocalCatalogue _catalogue;
  final Visibility _visibility;

  /// Lecture locale : filtre SQL (kind/mag/messier/search) puis enrichissement
  /// alt/az + filtre « visible maintenant » (GPS téléphone). `limit: 500` comme
  /// le comportement online précédent (pagination différée Macro 4).
  Future<List<CatalogObjectDto>> listObjects({
    String? search,
    double? maxMag,
    bool visibleNow = false,
    String? kind,
    bool messier = false,
  }) async {
    final filter = LocalCatalogFilter(
      kind: kind,
      search: search ?? '',
      maxMag: maxMag,
      messierOnly: messier,
      limit: 500,
    );
    final objects = _catalogue.listAll(filter);
    return _visibility.enrich(objects, visibleNow: visibleNow);
  }

  /// POST /goto — pointe la monture sur l'objet identifié par [id] (Pi).
  Future<void> goto(String id, {bool confirmSolar = false}) async {
    await api.postJson('/goto', {'id': id, 'confirm_solar': confirmSolar});
  }

  /// Abort : POST /stop.
  Future<void> abort() => api.stop();
}
