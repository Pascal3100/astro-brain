/// DTOs pour le wizard d'alignement 3 étoiles.
///
/// Miroir des modèles Pydantic backend (`backend/src/astro_brain/alignment/`).
library;

class StarDto {
  const StarDto({
    required this.id,
    required this.name,
    required this.ra,
    required this.dec,
    required this.mag,
  });

  final String id;
  final String name;
  final double ra;
  final double dec;
  final double mag;

  factory StarDto.fromJson(Map<String, dynamic> j) => StarDto(
        id: j['id'] as String,
        name: j['name'] as String,
        ra: (j['ra'] as num).toDouble(),
        dec: (j['dec'] as num).toDouble(),
        mag: (j['mag'] as num).toDouble(),
      );
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
    required this.startedAtUtc,
    required this.candidates,
    required this.selected,
    required this.records,
    required this.currentIdx,
  });

  final String sessionId;
  final String startedAtUtc;
  final List<StarDto> candidates;
  final List<StarDto> selected;
  final List<StarRecordDto?> records;
  final int currentIdx;

  factory AlignmentSessionDto.fromJson(Map<String, dynamic> j) {
    final candidates = (j['candidates'] as List)
        .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
        .toList();
    final selected = (j['selected'] as List)
        .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
        .toList();
    final records = (j['records'] as List)
        .map((e) => e == null
            ? null
            : StarRecordDto.fromJson(e as Map<String, dynamic>))
        .toList();
    return AlignmentSessionDto(
      sessionId: j['session_id'] as String,
      startedAtUtc: j['started_at_utc'] as String,
      candidates: candidates,
      selected: selected,
      records: records,
      currentIdx: j['current_idx'] as int,
    );
  }
}

class AlignmentModelDto {
  const AlignmentModelDto({
    required this.rmsArcmin,
    required this.residualsArcmin,
    required this.validatedAtUtc,
    required this.quality,
    required this.starIds,
  });

  final double rmsArcmin;
  final List<double> residualsArcmin;
  final String validatedAtUtc;
  final String quality;
  final List<String> starIds;

  factory AlignmentModelDto.fromJson(Map<String, dynamic> j) =>
      AlignmentModelDto(
        rmsArcmin: (j['rms_arcmin'] as num).toDouble(),
        residualsArcmin: (j['residuals_arcmin'] as List)
            .map((e) => (e as num).toDouble())
            .toList(),
        validatedAtUtc: j['validated_at_utc'] as String,
        quality: j['quality'] as String,
        starIds: (j['star_ids'] as List).map((e) => e as String).toList(),
      );

  /// ID de l'étoile dont le résidu dépasse 3× la moyenne des autres,
  /// ou `null` si aucune ne se distingue assez (cas typique : 3 étoiles
  /// alignées correctement, on ne propose pas d'outlier).
  String? get outlierId {
    if (residualsArcmin.length < 2) return null;
    var worstIdx = 0;
    var worst = residualsArcmin[0];
    for (var i = 1; i < residualsArcmin.length; i++) {
      if (residualsArcmin[i] > worst) {
        worst = residualsArcmin[i];
        worstIdx = i;
      }
    }
    var sumOthers = 0.0;
    for (var i = 0; i < residualsArcmin.length; i++) {
      if (i != worstIdx) sumOthers += residualsArcmin[i];
    }
    final meanOthers = sumOthers / (residualsArcmin.length - 1);
    if (meanOthers <= 0) return null;
    if (worst > 3 * meanOthers) return starIds[worstIdx];
    return null;
  }
}
