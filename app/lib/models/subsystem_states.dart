/// Enums miroirs des états publiés par le backend (voir spec v0.1, section
/// « Modèle d'état système »). Chaque enum expose `fromJson(String)` qui
/// accepte la valeur snake_case du backend et jette `FormatException` sur
/// une valeur inconnue.
library;

enum MountState {
  disconnected,
  connecting,
  ready,
  moving,
  error;

  static MountState fromJson(String v) => switch (v) {
        'disconnected' => MountState.disconnected,
        'connecting' => MountState.connecting,
        'ready' => MountState.ready,
        'moving' => MountState.moving,
        'error' => MountState.error,
        _ => throw FormatException('MountState inconnu: $v'),
      };
}

enum TrackingState {
  off,
  sidereal;

  static TrackingState fromJson(String v) => switch (v) {
        'off' => TrackingState.off,
        'sidereal' => TrackingState.sidereal,
        _ => throw FormatException('TrackingState inconnu: $v'),
      };
}

enum NetworkState {
  offline,
  client,
  hotspot;

  static NetworkState fromJson(String v) => switch (v) {
        'offline' => NetworkState.offline,
        'client' => NetworkState.client,
        'hotspot' => NetworkState.hotspot,
        _ => throw FormatException('NetworkState inconnu: $v'),
      };
}

enum SystemInfoState {
  ok,
  warning,
  critical;

  static SystemInfoState fromJson(String v) => switch (v) {
        'ok' => SystemInfoState.ok,
        'warning' => SystemInfoState.warning,
        'critical' => SystemInfoState.critical,
        _ => throw FormatException('SystemInfoState inconnu: $v'),
      };
}

enum AlignmentSubsysState {
  idle,
  active;

  static AlignmentSubsysState fromJson(String v) => switch (v) {
        'idle' => AlignmentSubsysState.idle,
        'active' => AlignmentSubsysState.active,
        _ => throw FormatException('AlignmentSubsysState inconnu: $v'),
      };
}
