/// Façade catalogue local — logique app-authored (listing, recherche,
/// filtrage) au-dessus de `reference.sqlite` en cache. Le backend ne résout
/// le catalogue que par id (`ReferenceCatalog.get_by_qualified_id`, pour le
/// GoTo) ; il n'a pas d'équivalent listing/recherche/filtrage.
library;

import '../catalogue_models.dart';
import 'catalogue_providers.dart';
import 'local_reference_db.dart';

class LocalCatalogue {
  LocalCatalogue({
    required LocalReferenceDb reference,
    required FixedObjectProvider fixed,
    required EphemerisProvider ephemeris,
  })  : _ref = reference,
        _fixed = fixed,
        _ephemeris = ephemeris;

  final LocalReferenceDb _ref;
  final FixedObjectProvider _fixed;
  final EphemerisProvider _ephemeris;

  List<CatalogObjectDto> listAll(LocalCatalogFilter f) {
    if (!_ref.ready) return [];
    if (f.kind != null) {
      if (FixedObjectProvider.kinds.contains(f.kind)) return _fixed.listObjects(f);
      if (EphemerisProvider.kinds.contains(f.kind)) return _ephemeris.listObjects(f);
      return [];
    }
    final widened = f.copyWith(limit: f.limit + f.offset, offset: 0);
    final merged = <CatalogObjectDto>[
      ..._fixed.listObjects(widened),
      ..._ephemeris.listObjects(widened),
    ];
    merged.sort((a, b) {
      final ma = a.mag ?? double.infinity;
      final mb = b.mag ?? double.infinity;
      final c = ma.compareTo(mb);
      return c != 0 ? c : a.name.compareTo(b.name);
    });
    final start = f.offset.clamp(0, merged.length);
    final end = (f.offset + f.limit).clamp(0, merged.length);
    return merged.sublist(start, end);
  }
}
