import 'dart:io';

import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/oracle_cache/almanac_store.dart';
import 'package:astro_brain/oracle_cache/wiring.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('buildOracleWiring construit le graphe local sans exception', () async {
    final tmp = Directory.systemTemp.createTempSync('wiring_test');
    addTearDown(() => tmp.deleteSync(recursive: true));
    final store = AlmanacStore(docsDir: () async => tmp);
    final w = await buildOracleWiring(store: store);
    // Aucun fichier reference.sqlite → base non prête, mais pas d'exception.
    expect(w.referenceDb.ready, isFalse);
    // Les deux repositories se construisent via le graphe.
    final refRepo = ReferenceRepository(reference: w.referenceDb, almanacSync: w.almanacSync);
    final status = await refRepo.getStatus();
    expect(status.ready, isFalse); // meta() == null → ready:false, pas de throw
    w.referenceDb.close();
  });
}
