/// DTOs miroir des routes `/reference/*` du backend
/// (`backend/astro_brain/routes/reference.py`).
library;

import 'package:equatable/equatable.dart';

class ReferenceStatusDto extends Equatable {
  const ReferenceStatusDto({
    required this.ready,
    this.schemaVersion,
    this.generatedAt,
    this.windowStart,
    this.windowEnd,
  });

  final bool ready;
  final int? schemaVersion;
  final String? generatedAt;
  final String? windowStart;
  final String? windowEnd;

  factory ReferenceStatusDto.fromJson(Map<String, dynamic> j) =>
      ReferenceStatusDto(
        ready: j['ready'] as bool? ?? false,
        schemaVersion: j['schema_version'] as int?,
        generatedAt: j['generated_at'] as String?,
        windowStart: j['window_start'] as String?,
        windowEnd: j['window_end'] as String?,
      );

  @override
  List<Object?> get props =>
      [ready, schemaVersion, generatedAt, windowStart, windowEnd];
}

class ReferenceSyncResultDto extends Equatable {
  const ReferenceSyncResultDto({required this.status, this.schemaVersion});

  final String status;
  final int? schemaVersion;

  factory ReferenceSyncResultDto.fromJson(Map<String, dynamic> j) =>
      ReferenceSyncResultDto(
        status: j['status'] as String? ?? 'unknown',
        schemaVersion: j['schema_version'] as int?,
      );

  @override
  List<Object?> get props => [status, schemaVersion];
}
