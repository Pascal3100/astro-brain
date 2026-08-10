import '../../../services/api_service.dart';
import 'reference_models.dart';

/// Façade REST sur les routes `/reference/*` (statut + resync de l'almanach).
class ReferenceRepository {
  ReferenceRepository({required this.api});

  final ApiService api;

  Future<ReferenceStatusDto> getStatus() async {
    final j = await api.getJson('/reference/status');
    return ReferenceStatusDto.fromJson(j);
  }

  Future<ReferenceSyncResultDto> sync() async {
    final j = await api.postJson('/reference/sync', const {});
    return ReferenceSyncResultDto.fromJson(j);
  }
}
