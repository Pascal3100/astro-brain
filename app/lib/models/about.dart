/// Modèle Dart miroir du payload `GET /about` du backend.
///
/// Correspondances JSON → Dart :
///   `backend_version`  → `backendVersion`
///   `mount_firmware`   → `mountFirmware`
///   `uptime_s`         → `uptimeS`
///   `started_at`       → `startedAt`
library;

import 'package:equatable/equatable.dart';

/// Informations système retournées par `GET /about`.
///
/// Tous les champs optionnels (`String?`, `int?`) peuvent être `null` en v0.2
/// (firmware toujours null ; ip/ssid null si hors réseau).
class AboutInfo extends Equatable {
  const AboutInfo({
    required this.backendVersion,
    this.mountFirmware,
    this.ip,
    this.ssid,
    this.uptimeS,
    this.startedAt,
  });

  final String backendVersion;

  /// Firmware de la monture — toujours `null` en v0.2.
  final String? mountFirmware;

  /// Adresse IP courante du Pi — `null` si hors réseau.
  final String? ip;

  /// SSID Wi-Fi courant — `null` si hors réseau.
  final String? ssid;

  /// Uptime du backend en secondes.
  final int? uptimeS;

  /// Timestamp de démarrage du backend (ISO 8601).
  final String? startedAt;

  factory AboutInfo.fromJson(Map<String, dynamic> json) => AboutInfo(
        backendVersion: json['backend_version'] as String,
        mountFirmware: json['mount_firmware'] as String?,
        ip: json['ip'] as String?,
        ssid: json['ssid'] as String?,
        uptimeS: json['uptime_s'] as int?,
        startedAt: json['started_at'] as String?,
      );

  @override
  List<Object?> get props => [
        backendVersion,
        mountFirmware,
        ip,
        ssid,
        uptimeS,
        startedAt,
      ];
}
