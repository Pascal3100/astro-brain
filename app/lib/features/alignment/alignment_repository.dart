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
}
