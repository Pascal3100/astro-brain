import 'package:astro_brain/models/subsystem_kind.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SubsystemKind.fromJson', () {
    test('parse les 4 kinds', () {
      expect(SubsystemKind.fromJson('mount'), SubsystemKind.mount);
      expect(SubsystemKind.fromJson('tracking'), SubsystemKind.tracking);
      expect(SubsystemKind.fromJson('network'), SubsystemKind.network);
      expect(SubsystemKind.fromJson('system'), SubsystemKind.system);
    });

    test('throws sur kind inconnu', () {
      expect(() => SubsystemKind.fromJson('camera'), throwsFormatException);
    });

    test('throws sur `gps`, retiré avec le module DroTek', () {
      expect(() => SubsystemKind.fromJson('gps'), throwsFormatException);
    });
  });
}
