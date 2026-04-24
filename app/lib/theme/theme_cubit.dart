import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Mode visuel de l'app Astro-Brain.
///
/// - [day]   : palette bleu spatial, usage en journée / lumière ambiante.
/// - [night] : palette rouge astro, préservation de la vision nocturne
///   (aucun bleu ni vert autorisé).
enum AstroThemeMode { day, night }

/// Cubit qui expose et fait basculer le [AstroThemeMode] courant.
///
/// Utilisé par le widget racine pour choisir entre `ThemeData` jour et nuit
/// via `MaterialApp.themeMode`.
///
/// Le dernier mode choisi est persisté via `shared_preferences` et restauré
/// automatiquement au démarrage.
class ThemeCubit extends Cubit<AstroThemeMode> {
  ThemeCubit({required SharedPreferences prefs})
      : _prefs = prefs,
        super(_read(prefs));

  static const _key = 'astro.theme.mode';
  final SharedPreferences _prefs;

  static AstroThemeMode _read(SharedPreferences p) {
    final v = p.getString(_key);
    return v == 'night' ? AstroThemeMode.night : AstroThemeMode.day;
  }

  /// Bascule jour ↔ nuit.
  void toggle() {
    final next = state == AstroThemeMode.day
        ? AstroThemeMode.night
        : AstroThemeMode.day;
    _prefs.setString(_key, next.name);
    emit(next);
  }

  void setDay() {
    _prefs.setString(_key, 'day');
    emit(AstroThemeMode.day);
  }

  void setNight() {
    _prefs.setString(_key, 'night');
    emit(AstroThemeMode.night);
  }
}
