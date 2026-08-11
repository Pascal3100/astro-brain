import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/oracle_cache/almanac_sync.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import '../../catalogue/local/_fixtures.dart';

class _MockSync extends Mock implements AlmanacSync {}

void main() {
  late _MockSync almanacSync;
  setUp(() => almanacSync = _MockSync());

  test('getStatus ready + fenêtre depuis la meta locale', () async {
    final ref = LocalReferenceDb.withDatabase(newReferenceDb());
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final s = await repo.getStatus();
    expect(s.ready, isTrue);
    expect(s.schemaVersion, 2);
    expect(s.windowEnd, '2026-09-30');
    ref.close();
  });

  test('getStatus ready:false si pas de fichier', () async {
    final ref = LocalReferenceDb('/nope/reference.sqlite')..open();
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final s = await repo.getStatus();
    expect(s.ready, isFalse);
    expect(s.generatedAt, isNull);
  });

  test('sync mappe le statut AlmanacSync → chaîne backend', () async {
    when(() => almanacSync.sync()).thenAnswer(
      (_) async =>
          const AlmanacSyncResult(AlmanacSyncStatus.updated, schemaVersion: 2),
    );
    final ref = LocalReferenceDb.withDatabase(newReferenceDb());
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final r = await repo.sync();
    expect(r.status, 'updated');
    expect(r.schemaVersion, 2);
    ref.close();
  });
}
