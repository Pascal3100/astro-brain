/// DTOs décrivant la copie LOCALE de l'almanach (`reference.sqlite` en cache
/// sur le téléphone), construits par `ReferenceRepository` à partir des
/// métadonnées du fichier local et du résultat de sync GitHub — pas un miroir
/// d'une réponse HTTP du backend.
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

  @override
  List<Object?> get props =>
      [ready, schemaVersion, generatedAt, windowStart, windowEnd];
}

class ReferenceSyncResultDto extends Equatable {
  const ReferenceSyncResultDto({required this.status, this.schemaVersion});

  final String status;
  final int? schemaVersion;

  @override
  List<Object?> get props => [status, schemaVersion];
}
