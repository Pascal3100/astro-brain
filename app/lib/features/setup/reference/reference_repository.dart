import '../../../oracle_cache/almanac_sync.dart';
import '../../catalogue/local/local_reference_db.dart';
import 'reference_models.dart';

/// Statut/resync de l'almanach LOCAL (reference.sqlite en cache). `getStatus`
/// lit la meta du fichier local ; `sync` télécharge depuis GitHub.
class ReferenceRepository {
  ReferenceRepository({
    required LocalReferenceDb reference,
    required AlmanacSync almanacSync,
  }) : _reference = reference,
       _almanacSync = almanacSync;

  final LocalReferenceDb _reference;
  final AlmanacSync _almanacSync;

  Future<ReferenceStatusDto> getStatus() async {
    final m = _reference.meta();
    if (m == null) return const ReferenceStatusDto(ready: false);
    return ReferenceStatusDto(
      ready: true,
      schemaVersion: m.schemaVersion,
      generatedAt: m.generatedAt,
      windowStart: m.windowStart,
      windowEnd: m.windowEnd,
    );
  }

  Future<ReferenceSyncResultDto> sync() async {
    final r = await _almanacSync.sync();
    return ReferenceSyncResultDto(
      status: _statusString(r.status),
      schemaVersion: r.schemaVersion,
    );
  }

  String _statusString(AlmanacSyncStatus s) => switch (s) {
    AlmanacSyncStatus.updated => 'updated',
    AlmanacSyncStatus.upToDate => 'up_to_date',
    AlmanacSyncStatus.offline => 'offline',
    AlmanacSyncStatus.rejectedSchema => 'rejected_schema',
    AlmanacSyncStatus.rejectedHash => 'rejected_hash',
  };
}
