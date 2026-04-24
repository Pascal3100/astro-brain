import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/theme_cubit.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

// NOTE : les tests qui invoquent AstroTheme.buildDay()/buildNight() ne sont
// pas ici — ces builders passent par google_fonts, qui fait un fetch HTTP
// à chaud. En environnement de test sans réseau, cela génère une erreur
// async non rattrapée. Cette validation se fait visuellement via
// `flutter run`. Quand on bundlera les TTF en assets locaux (plus tard),
// ces tests pourront être réactivés.

void main() {
  group('AppColors', () {
    test('palette jour ≠ palette nuit', () {
      expect(AppColors.day.accent, isNot(AppColors.night.accent));
      expect(AppColors.day.bgGradientTop, isNot(AppColors.night.bgGradientTop));
      expect(AppColors.day.dotOk, isNot(AppColors.night.dotOk));
    });

    test('copyWith remplace le champ ciblé et conserve les autres', () {
      final modified = AppColors.day.copyWith(accent: AppColors.night.accent);
      expect(modified.accent, AppColors.night.accent);
      expect(modified.bgGradientTop, AppColors.day.bgGradientTop);
    });
  });

  group('ThemeCubit', () {
    test('démarre en mode jour par défaut', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final cubit = ThemeCubit(prefs: prefs);
      expect(cubit.state, AstroThemeMode.day);
      cubit.close();
    });

    test('toggle bascule jour ↔ nuit', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final cubit = ThemeCubit(prefs: prefs);
      cubit.toggle();
      expect(cubit.state, AstroThemeMode.night);
      cubit.toggle();
      expect(cubit.state, AstroThemeMode.day);
      cubit.close();
    });

    test('setNight / setDay sont idempotents', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final cubit = ThemeCubit(prefs: prefs);
      cubit.setNight();
      cubit.setNight();
      expect(cubit.state, AstroThemeMode.night);
      cubit.setDay();
      expect(cubit.state, AstroThemeMode.day);
      cubit.close();
    });
  });
}
