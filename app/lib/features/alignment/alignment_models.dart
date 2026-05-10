/// DTOs pour le wizard d'alignement 3 étoiles.
///
/// Miroir des modèles Pydantic backend (`backend/astro_brain/models/alignment.py`).
library;

class StarDto {
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
}

class StarRecordDto {
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
}

class AlignmentSessionDto {
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
}

class AlignmentModelDto {
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

  /// ID de l'étoile dont le résidu dépasse 3× la moyenne des autres,
  /// ou `null` si aucune ne se distingue assez.
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
}
