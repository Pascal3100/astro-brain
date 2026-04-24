import 'package:astro_brain/models/overall_status.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OverallStatus.fromJson', () {
    test('parse les 4 valeurs émises par le backend', () {
      expect(OverallStatus.fromJson('green'), OverallStatus.green);
      expect(OverallStatus.fromJson('blue'), OverallStatus.blue);
      expect(OverallStatus.fromJson('orange'), OverallStatus.orange);
      expect(OverallStatus.fromJson('red'), OverallStatus.red);
    });

    test('throws sur "offline" (état app-side uniquement)', () {
      expect(() => OverallStatus.fromJson('offline'), throwsFormatException);
    });

    test('throws sur valeur inconnue', () {
      expect(() => OverallStatus.fromJson('bogus'), throwsFormatException);
    });
  });
}
