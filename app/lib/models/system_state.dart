import 'package:equatable/equatable.dart';

import 'overall_status.dart';
import 'subsystem_kind.dart';
import 'subsystem_state.dart';
import 'subsystem_states.dart';

/// État agrégé de tout le système côté backend. Source unique de vérité
/// pour l'UI (alimentée par le snapshot initial + les events SSE `update`).
class SystemState extends Equatable {
  const SystemState({
    required this.overall,
    required this.mount,
    required this.gps,
    required this.tracking,
    required this.network,
    required this.system,
    required this.seq,
    required this.ts,
    this.alignment,
  });

  final OverallStatus overall;
  final SubsystemState<MountState> mount;
  final SubsystemState<GpsState> gps;
  final SubsystemState<TrackingState> tracking;
  final SubsystemState<NetworkState> network;
  final SubsystemState<SystemInfoState> system;
  final SubsystemState<AlignmentSubsysState>? alignment;
  final int seq;
  final DateTime ts;

  /// `is_aligned` publié par le backend dans les détails du sous-système
  /// alignment. `false` si le sous-système est absent du snapshot.
  bool get isAligned => alignment?.details['is_aligned'] == true;

  /// `true` si un GoTo est en cours (détails du sous-système mount).
  bool get gotoInProgress => mount.details['goto_in_progress'] == true;

  /// Détails de la cible du GoTo courant, ou `null`.
  Map<String, dynamic>? get gotoTarget =>
      mount.details['goto'] as Map<String, dynamic>?;

  factory SystemState.fromJson(Map<String, dynamic> json) {
    final subs = json['subsystems'] as Map<String, dynamic>;
    return SystemState(
      overall: OverallStatus.fromJson(json['overall'] as String),
      mount: SubsystemState.fromJson(
          subs['mount'] as Map<String, dynamic>, MountState.fromJson),
      gps: SubsystemState.fromJson(
          subs['gps'] as Map<String, dynamic>, GpsState.fromJson),
      tracking: SubsystemState.fromJson(
          subs['tracking'] as Map<String, dynamic>, TrackingState.fromJson),
      network: SubsystemState.fromJson(
          subs['network'] as Map<String, dynamic>, NetworkState.fromJson),
      system: SubsystemState.fromJson(
          subs['system'] as Map<String, dynamic>, SystemInfoState.fromJson),
      alignment: subs['alignment'] == null
          ? null
          : SubsystemState.fromJson(
              subs['alignment'] as Map<String, dynamic>,
              AlignmentSubsysState.fromJson),
      seq: json['seq'] as int,
      ts: DateTime.parse(json['ts'] as String),
    );
  }

  /// Applique un event `update` SSE et renvoie une nouvelle [SystemState].
  /// Les autres sous-systèmes sont conservés.
  SystemState applyUpdate(Map<String, dynamic> update) {
    final kind = SubsystemKind.fromJson(update['subsystem'] as String);
    final stateJson = update['state'] as Map<String, dynamic>;
    final overall = OverallStatus.fromJson(update['overall'] as String);
    final seq = update['seq'] as int;
    final ts = DateTime.parse(update['ts'] as String);

    return SystemState(
      overall: overall,
      mount: kind == SubsystemKind.mount
          ? SubsystemState.fromJson(stateJson, MountState.fromJson)
          : mount,
      gps: kind == SubsystemKind.gps
          ? SubsystemState.fromJson(stateJson, GpsState.fromJson)
          : gps,
      tracking: kind == SubsystemKind.tracking
          ? SubsystemState.fromJson(stateJson, TrackingState.fromJson)
          : tracking,
      network: kind == SubsystemKind.network
          ? SubsystemState.fromJson(stateJson, NetworkState.fromJson)
          : network,
      system: kind == SubsystemKind.system
          ? SubsystemState.fromJson(stateJson, SystemInfoState.fromJson)
          : system,
      alignment: kind == SubsystemKind.alignment
          ? SubsystemState.fromJson(stateJson, AlignmentSubsysState.fromJson)
          : alignment,
      seq: seq,
      ts: ts,
    );
  }

  @override
  List<Object?> get props =>
      [overall, mount, gps, tracking, network, system, alignment, seq, ts];
}
