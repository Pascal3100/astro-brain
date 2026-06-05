import 'package:geolocator/geolocator.dart';

/// Abstraction légère de la position GPS du téléphone, mockable en tests.
///
/// La dépendance au plugin `geolocator` est isolée dans [GeolocatorPhoneLocation].
/// Les tests injectent un fake qui implémente cette interface directement,
/// sans jamais charger le plugin.
abstract class PhoneLocation {
  /// Retourne `(lat, lon)` ou `null` si la permission est refusée ou si
  /// la localisation est indisponible (timeout, capteur éteint, …).
  Future<({double lat, double lon})?> current();
}

/// Implémentation réelle utilisant le plugin `geolocator`.
///
/// Flux : vérification permission → demande si nécessaire → position courante.
/// Toute erreur est capturée et propagée comme `null` (l'appelant décide).
class GeolocatorPhoneLocation implements PhoneLocation {
  const GeolocatorPhoneLocation();

  @override
  Future<({double lat, double lon})?> current() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return null;
      }

      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 10),
        ),
      );
      return (lat: pos.latitude, lon: pos.longitude);
    } on Exception {
      return null;
    }
  }
}
