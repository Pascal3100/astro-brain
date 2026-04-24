/// Résolution de l'hôte du backend Astro-Brain.
///
/// Par défaut : `astro-brain.local:8000` (mDNS, résolvable sur le Wi-Fi local).
/// Quand on ajoutera un écran de config manuelle (hors v0.1), il devra
/// juste produire un [PiHost] différent et le passer au [RepositoryProvider]
/// racine — tout le reste reste inchangé.
class PiHost {
  const PiHost({this.host = 'astro-brain.local', this.port = 8000});

  final String host;
  final int port;

  Uri restUri(String path) => Uri.http('$host:$port', path);

  /// Les navigateurs / HttpClient mobiles gèrent bien SSE sur http:// local.
  /// TLS sera à considérer quand on sortira du réseau privé (hors v0.1).
  Uri sseUri(String path) => Uri.http('$host:$port', path);
}
