import 'package:shared_preferences/shared_preferences.dart';

const _kPrefsHost = 'astro.host';
const _kPrefsPort = 'astro.port';
const _defaultHost = String.fromEnvironment(
  'PI_HOST',
  defaultValue: 'astro-brain.local',
);
const _defaultPort = int.fromEnvironment('PI_PORT', defaultValue: 8000);

/// Résolution de l'hôte du backend Astro-Brain.
///
/// Précédence : `SharedPreferences` (clés [prefsHostKey] / [prefsPortKey],
/// écrites par l'écran Setup → Réseau) > `--dart-define=PI_HOST/PI_PORT`
/// > défauts mDNS (`astro-brain.local:8000`).
class PiHost {
  const PiHost({this.host = _defaultHost, this.port = _defaultPort});

  factory PiHost.fromPrefs(SharedPreferences prefs) {
    final h = prefs.getString(_kPrefsHost);
    final p = prefs.getInt(_kPrefsPort);
    return PiHost(host: h ?? _defaultHost, port: p ?? _defaultPort);
  }

  final String host;
  final int port;

  /// Construit l'URI REST. Les paramètres de requête doivent passer par
  /// [query] (et non être collés dans [path]) : `Uri.http` encode alors
  /// correctement clés et valeurs. Coller `?x=y` dans [path] ferait encoder
  /// le `?` en `%3F` → chemin invalide (404).
  Uri restUri(String path, [Map<String, dynamic>? query]) =>
      Uri.http('$host:$port', path, query);
  Uri sseUri(String path) => Uri.http('$host:$port', path);

  static const String prefsHostKey = _kPrefsHost;
  static const String prefsPortKey = _kPrefsPort;
}
