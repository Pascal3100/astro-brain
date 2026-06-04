/// DTOs pour le wizard d'alignement 3 étoiles.
///
/// Miroir des modèles Pydantic backend (`backend/astro_brain/models/alignment.py`).
library;

import 'package:equatable/equatable.dart';

class StarDto extends Equatable {
  const StarDto({
    required this.id,
    required this.name,
    required this.bayer,
    required this.raDeg,
    required this.decDeg,
    required this.mag,
  });

  final String id;
  final String name;
  final String bayer;
  final double raDeg;
  final double decDeg;
  final double mag;

  factory StarDto.fromJson(Map<String, dynamic> j) => StarDto(
    id: j['id'] as String,
    name: j['name'] as String,
    bayer: j['bayer'] as String,
    raDeg: (j['ra_deg'] as num).toDouble(),
    decDeg: (j['dec_deg'] as num).toDouble(),
    mag: (j['mag'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'bayer': bayer,
    'ra_deg': raDeg,
    'dec_deg': decDeg,
    'mag': mag,
  };

  @override
  List<Object?> get props => [id, name, bayer, raDeg, decDeg, mag];
}

class StarRecordDto extends Equatable {
  const StarRecordDto({
    required this.starId,
    required this.skyAz,
    required this.skyAlt,
    required this.mountAz,
    required this.mountAlt,
  });

  final String starId;
  final double skyAz;
  final double skyAlt;
  final double mountAz;
  final double mountAlt;

  factory StarRecordDto.fromJson(Map<String, dynamic> j) => StarRecordDto(
    starId: j['star_id'] as String,
    skyAz: (j['sky_az'] as num).toDouble(),
    skyAlt: (j['sky_alt'] as num).toDouble(),
    mountAz: (j['mount_az'] as num).toDouble(),
    mountAlt: (j['mount_alt'] as num).toDouble(),
  );

  @override
  List<Object?> get props => [starId, skyAz, skyAlt, mountAz, mountAlt];
}

class AlignmentSessionDto extends Equatable {
  const AlignmentSessionDto({
    required this.sessionId,
    required this.candidates,
    required this.recordedStars,
    required this.currentIdx,
  });

  final String sessionId;
  final List<StarDto> candidates;
  final List<StarRecordDto> recordedStars;
  final int currentIdx;

  factory AlignmentSessionDto.fromJson(Map<String, dynamic> j) =>
      AlignmentSessionDto(
        sessionId: j['session_id'] as String,
        candidates: (j['candidates'] as List)
            .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        recordedStars: (j['recorded_stars'] as List? ?? [])
            .map((e) => StarRecordDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        currentIdx: j['current_idx'] as int,
      );

  @override
  List<Object?> get props => [sessionId, candidates, recordedStars, currentIdx];
}

class AlignmentModelDto extends Equatable {
  const AlignmentModelDto({
    required this.recordedStars,
    required this.rmsArcmin,
    required this.residuals,
    required this.validatedAtUtc,
    required this.quality,
  });

  final List<StarRecordDto> recordedStars;
  final double rmsArcmin;
  final Map<String, double> residuals;
  final String validatedAtUtc;
  final String quality;

  factory AlignmentModelDto.fromJson(Map<String, dynamic> j) =>
      AlignmentModelDto(
        recordedStars: (j['recorded_stars'] as List)
            .map((e) => StarRecordDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        rmsArcmin: (j['rms_arcmin'] as num).toDouble(),
        residuals: (j['residuals'] as Map).map(
          (k, v) => MapEntry(k as String, (v as num).toDouble()),
        ),
        validatedAtUtc: j['validated_at_utc'] as String,
        quality: j['quality'] as String,
      );

  /// ID de l'étoile dont le résiduel domine — heuristique : résidu > 3× la
  /// moyenne des autres. Utilisé par ValidationScreen pour précâbler
  /// "REFAIRE <ÉTOILE>". `null` si la dispersion n'est pas concluante
  /// (< 2 résidus, ou pic non distinct).
  String? get outlierId {
    if (residuals.isEmpty) return null;
    final entries = residuals.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final worst = entries.first;
    final others = entries.skip(1).toList();
    if (others.isEmpty) return null;
    final mean =
        others.map((e) => e.value).reduce((a, b) => a + b) / others.length;
    return worst.value > 3 * mean ? worst.key : null;
  }

  @override
  List<Object?> get props => [
    recordedStars,
    rmsArcmin,
    residuals,
    validatedAtUtc,
    quality,
  ];
}

/// Nœud d'une figure de constellation (étoile avec coordonnées optionnelles Az/Alt).
class ConstellationNodeDto extends Equatable {
  const ConstellationNodeDto({
    required this.label,
    required this.mag,
    required this.raDeg,
    required this.decDeg,
    this.az,
    this.alt,
    required this.isTarget,
  });

  final String label;
  final double mag;
  final double raDeg;
  final double decDeg;

  /// `null` si la constellation n'est pas encore orientée (az/alt non calculés).
  final double? az;

  /// `null` si la constellation n'est pas encore orientée (az/alt non calculés).
  final double? alt;

  final bool isTarget;

  factory ConstellationNodeDto.fromJson(Map<String, dynamic> j) =>
      ConstellationNodeDto(
        label: j['label'] as String,
        mag: (j['mag'] as num).toDouble(),
        raDeg: (j['ra_deg'] as num).toDouble(),
        decDeg: (j['dec_deg'] as num).toDouble(),
        az: (j['az'] as num?)?.toDouble(),
        alt: (j['alt'] as num?)?.toDouble(),
        isTarget: j['is_target'] as bool,
      );

  @override
  List<Object?> get props => [label, mag, raDeg, decDeg, az, alt, isTarget];
}

/// Figure d'une constellation : graphe de nœuds reliés par des segments.
///
/// Miroir de `ConstellationFigure` backend (`backend/astro_brain/models/alignment.py`).
class ConstellationFigureDto extends Equatable {
  const ConstellationFigureDto({
    required this.abbr,
    required this.name,
    required this.oriented,
    required this.nodes,
    required this.segments,
  });

  final String abbr;
  final String name;

  /// `true` si [nodes] contiennent des coordonnées Az/Alt calculées.
  final bool oriented;

  final List<ConstellationNodeDto> nodes;

  /// Liste de paires `[indexA, indexB]` reliant des nœuds dans [nodes].
  final List<List<int>> segments;

  factory ConstellationFigureDto.fromJson(Map<String, dynamic> j) =>
      ConstellationFigureDto(
        abbr: j['abbr'] as String,
        name: j['name'] as String,
        oriented: j['oriented'] as bool,
        nodes: (j['nodes'] as List)
            .map((e) => ConstellationNodeDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        segments: (j['segments'] as List)
            .map((e) => (e as List).map((i) => i as int).toList())
            .toList(),
      );

  @override
  List<Object?> get props => [abbr, name, oriented, nodes, segments];
}
