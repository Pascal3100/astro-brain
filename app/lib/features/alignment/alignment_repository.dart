import '../../services/api_service.dart';
import 'alignment_models.dart';

/// Façade REST sur le router `/align/*` du backend.
class AlignmentRepository {
  AlignmentRepository({required ApiService api}) : _api = api;

  final ApiService _api;

  /// GET /align/session — `null` si aucune session active.
  Future<AlignmentSessionDto?> getSession() async {
    final j = await _api.getJson('/align/session');
    final raw = j['session'];
    if (raw == null) return null;
    return AlignmentSessionDto.fromJson(raw as Map<String, dynamic>);
  }

  /// POST /align/start avec la liste des 3 IDs d'étoiles sélectionnées.
  Future<AlignmentSessionDto> start(List<String> starIds) async {
    final j = await _api.postJson('/align/start', {'star_ids': starIds});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/swap/{idx} — remplace l'étoile à [idx] par [starId].
  Future<AlignmentSessionDto> swap(int idx, String starId) async {
    final j = await _api.postJson('/align/swap/$idx', {'star_id': starId});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/record — capture la position monture pour l'étoile [idx].
  Future<AlignmentSessionDto> record(int idx) async {
    final j = await _api.postJson('/align/record', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/restart_star — efface l'enregistrement [idx] pour
  /// recommencer la capture.
  Future<AlignmentSessionDto> restartStar(int idx) async {
    final j = await _api.postJson('/align/restart_star', {'idx': idx});
    return AlignmentSessionDto.fromJson(j);
  }

  /// POST /align/finalize — calcule le modèle SVD et le persiste.
  Future<AlignmentModelDto> finalize() async {
    final j = await _api.postJson('/align/finalize', <String, dynamic>{});
    return AlignmentModelDto.fromJson(j);
  }

  /// DELETE /align/session — annule la session en cours.
  Future<void> cancel() => _api.delete('/align/session');
}
