/// DTO miroir du `CatalogObject` Pydantic backend
/// (`backend/astro_brain/services/catalog/models.py`).
library;

import 'package:equatable/equatable.dart';

class CatalogObjectDto extends Equatable {
  const CatalogObjectDto({
    required this.qualifiedId,
    required this.kind,
    required this.name,
    required this.raDeg,
    required this.decDeg,
    this.designation,
    this.mag,
    this.constellation,
    this.objectType,
    this.altitudeDeg,
    this.azimuthDeg,
  });

  final String qualifiedId;
  final String kind;
  final String name;
  final double raDeg;
  final double decDeg;
  final String? designation;
  final double? mag;
  final String? constellation;
  final String? objectType;
  final double? altitudeDeg;
  final double? azimuthDeg;

  /// `true` si l'altitude courante est connue et au-dessus de l'horizon.
  bool get isVisible => altitudeDeg != null && altitudeDeg! > 0.0;

  factory CatalogObjectDto.fromJson(Map<String, dynamic> j) => CatalogObjectDto(
        qualifiedId: j['qualified_id'] as String,
        kind: j['kind'] as String,
        name: j['name'] as String,
        raDeg: (j['ra_deg'] as num).toDouble(),
        decDeg: (j['dec_deg'] as num).toDouble(),
        designation: j['designation'] as String?,
        mag: (j['mag'] as num?)?.toDouble(),
        constellation: j['constellation'] as String?,
        objectType: j['object_type'] as String?,
        altitudeDeg: (j['altitude_deg'] as num?)?.toDouble(),
        azimuthDeg: (j['azimuth_deg'] as num?)?.toDouble(),
      );

  @override
  List<Object?> get props => [
        qualifiedId, kind, name, raDeg, decDeg, designation, mag,
        constellation, objectType, altitudeDeg, azimuthDeg,
      ];
}
