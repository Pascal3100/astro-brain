import '../../services/api_service.dart';
import 'alignment_models.dart';

/// Façade REST sur le router `/align/*` du backend.
class AlignmentRepository {
  AlignmentRepository({required this.api});

  final ApiService api;

  /// GET /align/session — `null` si aucune session active.
  Future<AlignmentSessionDto?> getSession() async {
    final j = await api.getJson('/align/session');
    final raw = j['session'];
    if (raw == null) return null;
    return AlignmentSessionDto.fromJson(raw as Map<String, dynamic>);
  }

  /// POST /align/start — démarre une nouvelle session.
  Future<AlignmentSessionDto> start() async {
    final j = await api.postJson('/align/start', const {});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/swap/{idx} — remplace l'étoile à [idx] par [star].
  Future<AlignmentSessionDto> swap(int idx, StarDto star) async {
    final j = await api.postJson('/align/swap/$idx', {'star': star.toJson()});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/record — capture la position monture pour l'étoile [idx].
  Future<AlignmentSessionDto> record(int idx) async {
    final j = await api.postJson('/align/record', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/restart_star — efface l'enregistrement [idx] pour
  /// recommencer la capture.
  Future<AlignmentSessionDto> restartStar(int idx) async {
    final j = await api.postJson('/align/restart_star', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/finalize — calcule le modèle SVD et le persiste.
  Future<AlignmentModelDto> finalize() async {
    final j = await api.postJson('/align/finalize', const {});
    return AlignmentModelDto.fromJson(j);
  }

  /// DELETE /align/session — annule la session en cours.
  Future<void> cancel() => api.delete('/align/session');

  /// GET /align/constellation/{abbr}?target_ra=..&target_dec=..
  ///
  /// [raDeg] et [decDeg] sont les coordonnées de l'étoile cible ; le backend
  /// s'en sert pour orienter la figure (calcul Az/Alt). Les paramètres passent
  /// par [query] afin que `Uri.http` les encode correctement — coller `?…`
  /// dans le chemin ferait encoder le `?` en `%3F` → 404 (cf. commit f179db4).
  Future<ConstellationFigureDto> fetchConstellation(
    String abbr, {
    required double raDeg,
    required double decDeg,
  }) async {
    final j = await api.getJson(
      '/align/constellation/$abbr',
      query: {
        'target_ra': raDeg.toString(),
        'target_dec': decDeg.toString(),
      },
    );
    return ConstellationFigureDto.fromJson(j);
  }

  /// GET /align/stars/visible → `{constellations: {abbr: [star,…]}}`.
  ///
  /// Retourne une map `abbr → List<StarDto>` pour toutes les constellations
  /// actuellement visibles (au-dessus de l'horizon du backend).
  Future<Map<String, List<StarDto>>> fetchVisibleStars() async {
    final j = await api.getJson('/align/stars/visible');
    final raw = j['constellations'] as Map<String, dynamic>;
    return raw.map(
      (abbr, list) => MapEntry(
        abbr,
        (list as List)
            .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
            .toList(),
      ),
    );
  }

  /// POST /align/location/client {lat, lon} — transmet la position GPS du
  /// téléphone au backend (utilisé quand le GPS du Pi est indisponible).
  Future<void> postClientLocation(double lat, double lon) =>
      api.postJson('/align/location/client', {'lat': lat, 'lon': lon});
}
