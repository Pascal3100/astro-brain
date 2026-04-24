import 'dart:convert';

import 'package:astro_brain/models/overall_status.dart';
import 'package:astro_brain/models/subsystem_states.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:flutter_test/flutter_test.dart';

const _snapshot = '''
{
  "overall": "green",
  "subsystems": {
    "mount": {"state": "ready", "details": {"firmware_version": "11.01"}, "since": "2026-04-17T20:31:12Z", "message": null},
    "gps": {"state": "fix_3d", "details": {"lat": 48.8566, "lon": 2.3522, "altitude_m": 45, "satellites": 8, "hdop": 0.9}, "since": "2026-04-17T20:30:00Z", "message": null},
    "tracking": {"state": "sidereal", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "network": {"state": "client", "details": {"ssid": "BoxWifi", "ip": "192.168.1.42"}, "since": "2026-04-17T20:29:00Z", "message": null},
    "system": {"state": "ok", "details": {"cpu_temp_c": 58.2, "cpu_load": 0.42, "uptime_s": 8120}, "since": "2026-04-17T20:29:00Z", "message": null}
  },
  "seq": 142,
  "ts": "2026-04-17T20:31:12Z"
}
''';

void main() {
  group('SystemState.fromJson', () {
    test('parse un snapshot complet', () {
      final state = SystemState.fromJson(
          jsonDecode(_snapshot) as Map<String, dynamic>);

      expect(state.overall, OverallStatus.green);
      expect(state.seq, 142);
      expect(state.mount.state, MountState.ready);
      expect(state.mount.details['firmware_version'], '11.01');
      expect(state.gps.state, GpsState.fix3d);
      expect(state.gps.details['satellites'], 8);
      expect(state.tracking.state, TrackingState.sidereal);
      expect(state.network.state, NetworkState.client);
      expect(state.system.state, SystemInfoState.ok);
    });

    test('applyUpdate remplace un sous-système et incrémente seq', () {
      final initial = SystemState.fromJson(
          jsonDecode(_snapshot) as Map<String, dynamic>);
      final updatedJson = {
        'subsystem': 'gps',
        'state': {
          'state': 'searching',
          'details': {'satellites': 3},
          'since': '2026-04-17T20:32:00Z',
          'message': null,
        },
        'overall': 'orange',
        'seq': 143,
        'ts': '2026-04-17T20:32:00Z',
      };
      final next = initial.applyUpdate(updatedJson);
      expect(next.gps.state, GpsState.searching);
      expect(next.gps.details['satellites'], 3);
      expect(next.overall, OverallStatus.orange);
      expect(next.seq, 143);
      expect(next.mount.state, MountState.ready);
    });
  });
}
