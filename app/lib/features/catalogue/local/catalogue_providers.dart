/// Providers catalogue lus dans reference.sqlite local — logique app-authored
/// (le backend ne résout le catalogue que par id, pour le GoTo ; il n'a pas
/// de providers de listing/recherche équivalents).
library;

import 'package:sqlite3/sqlite3.dart';

import '../catalogue_models.dart';
import 'ephemeris_interpolation.dart';
import 'local_reference_db.dart';

class LocalCatalogFilter {
  const LocalCatalogFilter({
    this.kind,
    this.search = '',
    this.maxMag,
    this.messierOnly = false,
    this.limit = 500,
    this.offset = 0,
  });
  final String? kind;
  final String search;
  final double? maxMag;
  final bool messierOnly;
  final int limit;
  final int offset;

  LocalCatalogFilter copyWith({int? limit, int? offset}) => LocalCatalogFilter(
        kind: kind, search: search, maxMag: maxMag, messierOnly: messierOnly,
        limit: limit ?? this.limit, offset: offset ?? this.offset);
}

const _fixedColumns =
    'o.id, o.kind, o.name, o.designation, f.ra_deg, f.dec_deg, f.apparent_mag,'
    ' f.object_type, f.size_arcmin, f.constellation, f.messier, f.ngc_ic';

CatalogObjectDto _fixedRow(Row r) => CatalogObjectDto(
      qualifiedId: r['id'] as String,
      kind: r['kind'] as String,
      name: (r['name'] as String?) ??
          (r['designation'] as String?) ??
          (r['id'] as String),
      designation: r['designation'] as String?,
      raDeg: (r['ra_deg'] as num).toDouble(),
      decDeg: (r['dec_deg'] as num).toDouble(),
      mag: (r['apparent_mag'] as num?)?.toDouble(),
      constellation: r['constellation'] as String?,
      objectType: r['object_type'] as String?,
      angularSizeArcmin: (r['size_arcmin'] as num?)?.toDouble(),
      messier: r['messier'] as String?,
      ngcIc: r['ngc_ic'] as String?,
    );

class FixedObjectProvider {
  FixedObjectProvider(this._ref);
  static const kinds = {'dso', 'star'};
  final LocalReferenceDb _ref;

  List<CatalogObjectDto> listObjects(LocalCatalogFilter f) {
    final conn = _ref.current();
    if (conn == null) return [];
    var sql = 'SELECT $_fixedColumns FROM fixed_object f'
        ' JOIN objects o ON o.id = f.object_id WHERE ';
    final params = <Object?>[];
    if (kinds.contains(f.kind)) {
      sql += 'o.kind = ?';
      params.add(f.kind);
    } else {
      sql += "o.kind IN ('dso', 'star')";
    }
    if (f.maxMag != null) {
      sql += ' AND f.apparent_mag IS NOT NULL AND f.apparent_mag <= ?';
      params.add(f.maxMag);
    }
    if (f.messierOnly) sql += ' AND f.messier IS NOT NULL';
    if (f.search.isNotEmpty) {
      final like = '%${f.search}%';
      sql += ' AND (o.name LIKE ? OR o.designation LIKE ?'
          ' OR f.messier LIKE ? OR f.ngc_ic LIKE ?)';
      params.addAll([like, like, like, like]);
    }
    sql += ' ORDER BY CASE WHEN f.apparent_mag IS NULL THEN 1 ELSE 0 END,'
        ' f.apparent_mag, o.name LIMIT ? OFFSET ?';
    params.addAll([f.limit, f.offset]);
    return conn.select(sql, params).map(_fixedRow).toList();
  }
}

class EphemerisProvider {
  EphemerisProvider(this._ref, {required DateTime Function() nowUtc})
      : _now = nowUtc;
  static const kinds = {'comet', 'planet', 'moon', 'sun'};
  final LocalReferenceDb _ref;
  final DateTime Function() _now;

  List<CatalogObjectDto> listObjects(LocalCatalogFilter f) {
    final conn = _ref.current();
    if (conn == null) return [];
    final now = _now();
    final (clause, kindParams) = _kindsClause(f);
    final lo = now.subtract(const Duration(days: 1, hours: 12)).toIso8601String();
    final hi = now.add(const Duration(days: 1, hours: 12)).toIso8601String();
    final rows = conn.select(
      'SELECT e.object_id, o.kind, o.name, o.designation, e.sample_utc,'
      ' e.ra_deg, e.dec_deg, e.apparent_mag, e.illumination, e.constellation'
      ' FROM ephemeris e JOIN objects o ON o.id = e.object_id'
      ' WHERE $clause AND e.sample_utc BETWEEN ? AND ?'
      ' ORDER BY e.object_id, e.sample_utc',
      [...kindParams, lo, hi],
    );
    final grouped = <String, List<Row>>{};
    for (final r in rows) {
      grouped.putIfAbsent(r['object_id'] as String, () => []).add(r);
    }
    final objs = <CatalogObjectDto>[];
    for (final samples in grouped.values) {
      final obj = _build(samples, now);
      if (obj == null || obj.ephemerisStale) continue;
      if (f.maxMag != null && (obj.mag == null || obj.mag! > f.maxMag!)) continue;
      if (f.search.isNotEmpty) {
        final hay = '${obj.name} ${obj.designation ?? ''}'.toLowerCase();
        if (!hay.contains(f.search.toLowerCase())) continue;
      }
      objs.add(obj);
    }
    objs.sort((a, b) => _magKey(a).compareTo(_magKey(b)) != 0
        ? _magKey(a).compareTo(_magKey(b))
        : a.name.compareTo(b.name));
    final start = f.offset.clamp(0, objs.length);
    final end = (f.offset + f.limit).clamp(0, objs.length);
    return objs.sublist(start, end);
  }

  double _magKey(CatalogObjectDto o) => o.mag ?? double.infinity;

  (String, List<Object?>) _kindsClause(LocalCatalogFilter f) {
    if (kinds.contains(f.kind)) return ('o.kind = ?', [f.kind]);
    final ph = List.filled(kinds.length, '?').join(', ');
    return ('o.kind IN ($ph)', kinds.toList());
  }

  CatalogObjectDto? _build(List<Row> samples, DateTime now) {
    if (samples.isEmpty) return null;
    final parsed = samples
        .map((s) => (parseUtc(s['sample_utc'] as String), s))
        .toList();
    final before = parsed.where((p) => !p.$1.isAfter(now)).toList();
    final after = parsed.where((p) => !p.$1.isBefore(now)).toList();
    final stale = !(before.isNotEmpty && after.isNotEmpty);
    late Row src;
    late double ra, dec;
    if (!stale) {
      final b = before.last, a = after.first;
      final r = interpolateRaDec(
        (b.$1, (b.$2['ra_deg'] as num).toDouble(), (b.$2['dec_deg'] as num).toDouble()),
        (a.$1, (a.$2['ra_deg'] as num).toDouble(), (a.$2['dec_deg'] as num).toDouble()),
        now,
      );
      ra = r.ra;
      dec = r.dec;
      src = b.$2;
    } else {
      parsed.sort((x, y) => x.$1.difference(now).abs().compareTo(
          y.$1.difference(now).abs()));
      src = parsed.first.$2;
      ra = (src['ra_deg'] as num).toDouble();
      dec = (src['dec_deg'] as num).toDouble();
    }
    return CatalogObjectDto(
      qualifiedId: src['object_id'] as String,
      kind: src['kind'] as String,
      name: (src['name'] as String?) ??
          (src['designation'] as String?) ??
          (src['object_id'] as String),
      designation: src['designation'] as String?,
      raDeg: ra,
      decDeg: dec,
      mag: (src['apparent_mag'] as num?)?.toDouble(),
      illumination: (src['illumination'] as num?)?.toDouble(),
      constellation: src['constellation'] as String?,
      ephemerisStale: stale,
    );
  }
}
