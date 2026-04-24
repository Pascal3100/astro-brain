import 'package:astro_brain/models/subsystem_states.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MountState.fromJson', () {
    test('parse les 5 valeurs valides', () {
      expect(MountState.fromJson('disconnected'), MountState.disconnected);
      expect(MountState.fromJson('connecting'), MountState.connecting);
      expect(MountState.fromJson('ready'), MountState.ready);
      expect(MountState.fromJson('moving'), MountState.moving);
      expect(MountState.fromJson('error'), MountState.error);
    });

    test('throws sur une valeur inconnue', () {
      expect(() => MountState.fromJson('foo'), throwsFormatException);
    });
  });

  group('GpsState.fromJson', () {
    test('parse les 5 valeurs valides', () {
      expect(GpsState.fromJson('off'), GpsState.off);
      expect(GpsState.fromJson('no_fix'), GpsState.noFix);
      expect(GpsState.fromJson('searching'), GpsState.searching);
      expect(GpsState.fromJson('fix_2d'), GpsState.fix2d);
      expect(GpsState.fromJson('fix_3d'), GpsState.fix3d);
    });

    test('throws sur une valeur inconnue', () {
      expect(() => GpsState.fromJson('bogus'), throwsFormatException);
    });
  });

  group('TrackingState.fromJson', () {
    test('parse off / sidereal', () {
      expect(TrackingState.fromJson('off'), TrackingState.off);
      expect(TrackingState.fromJson('sidereal'), TrackingState.sidereal);
    });

    test('throws sur une valeur inconnue', () {
      expect(() => TrackingState.fromJson('bogus'), throwsFormatException);
    });
  });

  group('NetworkState.fromJson', () {
    test('parse les 3 valeurs', () {
      expect(NetworkState.fromJson('offline'), NetworkState.offline);
      expect(NetworkState.fromJson('client'), NetworkState.client);
      expect(NetworkState.fromJson('hotspot'), NetworkState.hotspot);
    });

    test('throws sur une valeur inconnue', () {
      expect(() => NetworkState.fromJson('bogus'), throwsFormatException);
    });
  });

  group('SystemInfoState.fromJson', () {
    test('parse ok / warning / critical', () {
      expect(SystemInfoState.fromJson('ok'), SystemInfoState.ok);
      expect(SystemInfoState.fromJson('warning'), SystemInfoState.warning);
      expect(SystemInfoState.fromJson('critical'), SystemInfoState.critical);
    });

    test('throws sur une valeur inconnue', () {
      expect(() => SystemInfoState.fromJson('bogus'), throwsFormatException);
    });
  });
}
