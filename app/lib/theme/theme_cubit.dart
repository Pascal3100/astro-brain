import 'package:flutter_bloc/flutter_bloc.dart';

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
/// Persistance (ex. dernier mode choisi) : à ajouter plus tard via
/// `shared_preferences`. Pour l'instant le mode défaut est `day`.
class ThemeCubit extends Cubit<AstroThemeMode> {
  ThemeCubit({AstroThemeMode initial = AstroThemeMode.day}) : super(initial);

  /// Bascule jour ↔ nuit.
  void toggle() => emit(
        state == AstroThemeMode.day ? AstroThemeMode.night : AstroThemeMode.day,
      );

  void setDay() => emit(AstroThemeMode.day);
  void setNight() => emit(AstroThemeMode.night);
}
