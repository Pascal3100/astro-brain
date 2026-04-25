import 'package:astro_brain/utils/mount_error_messages.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('humanizeMountMessage', () {
    test('null reste null', () {
      expect(humanizeMountMessage(null), isNull);
    });

    test('chaîne vide passe inchangée', () {
      expect(humanizeMountMessage(''), '');
    });

    test('Errno 2 sur /dev/ttyUSB → message humain', () {
      const raw =
          "[Errno 2] could not open port /dev/ttyUSB0: [Errno 2] No such file or directory: '/dev/ttyUSB0'";
      expect(
        humanizeMountMessage(raw),
        'Monture non détectée — vérifie le câble USB.',
      );
    });

    test('permission denied sur tty → libellé permission', () {
      expect(
        humanizeMountMessage('Permission denied: /dev/ttyACM0'),
        'Accès refusé au port série de la monture.',
      );
    });

    test('timeout générique → libellé pas de réponse', () {
      expect(
        humanizeMountMessage('serial read timed out after 5s'),
        'Pas de réponse de la monture — réessaye le branchement.',
      );
    });

    test('pattern inconnu → message brut conservé', () {
      const raw = 'firmware checksum mismatch on response 0xA5';
      expect(humanizeMountMessage(raw), raw);
    });
  });
}
