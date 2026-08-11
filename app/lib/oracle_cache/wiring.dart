/// Graphe DI du catalogue local (moteur + sync). Construit une fois au boot
/// dans main(), injecté dans AstroBrainApp. Isolé ici pour rester testable
/// sans monter le MaterialApp complet.
library;

import '../features/alignment/phone_location.dart';
import '../features/catalogue/local/catalogue_providers.dart';
import '../features/catalogue/local/local_catalogue.dart';
import '../features/catalogue/local/local_reference_db.dart';
import '../features/catalogue/local/visibility.dart';
import 'almanac_store.dart';
import 'almanac_sync.dart';

class OracleWiring {
  OracleWiring({
    required this.store,
    required this.referenceDb,
    required this.almanacSync,
    required this.catalogue,
    required this.visibility,
  });
  final AlmanacStore store;
  final LocalReferenceDb referenceDb;
  final AlmanacSync almanacSync;
  final LocalCatalogue catalogue;
  final Visibility visibility;
}

/// Construit le graphe local. Résout le chemin de reference.sqlite (async via
/// path_provider), ouvre la base en lecture seule (silencieux si absente).
Future<OracleWiring> buildOracleWiring({AlmanacStore? store}) async {
  final s = store ?? AlmanacStore();
  final referenceDb = LocalReferenceDb((await s.file()).path)..open();
  final almanacSync = AlmanacSync(store: s, reference: referenceDb);
  final catalogue = LocalCatalogue(
    reference: referenceDb,
    fixed: FixedObjectProvider(referenceDb),
    ephemeris: EphemerisProvider(referenceDb, nowUtc: () => DateTime.now().toUtc()),
  );
  final visibility = Visibility(location: const GeolocatorPhoneLocation());
  return OracleWiring(
    store: s,
    referenceDb: referenceDb,
    almanacSync: almanacSync,
    catalogue: catalogue,
    visibility: visibility,
  );
}
