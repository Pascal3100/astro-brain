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

Map<String, dynamic> _update({
  required String kind,
  required Map<String, dynamic> stateJson,
  String overall = 'green',
  int seq = 200,
  String ts = '2026-04-17T20:35:00Z',
}) =>
    {
      'subsystem': kind,
      'state': stateJson,
      'overall': overall,
      'seq': seq,
      'ts': ts,
    };

SystemState _initial() =>
    SystemState.fromJson(jsonDecode(_snapshot) as Map<String, dynamic>);

void main() {
  group('SystemState.fromJson', () {
    test('parse un snapshot complet', () {
      final state = _initial();

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
      final initial = _initial();
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

  group('SystemState.applyUpdate (multi-subsystems)', () {
    test('update mount → MountState.moving, gps intact', () {
      final initial = _initial();
      final next = initial.applyUpdate(_update(
        kind: 'mount',
        stateJson: {
          'state': 'moving',
          'details': {'firmware_version': '11.01'},
          'since': '2026-04-17T20:35:00Z',
          'message': null,
        },
      ));
      expect(next.mount.state, MountState.moving);
      expect(next.gps, initial.gps);
      expect(next.system, initial.system);
    });

    test('update tracking → TrackingState.off, mount intact', () {
      final initial = _initial();
      final next = initial.applyUpdate(_update(
        kind: 'tracking',
        stateJson: {
          'state': 'off',
          'details': <String, dynamic>{},
          'since': '2026-04-17T20:35:00Z',
          'message': null,
        },
      ));
      expect(next.tracking.state, TrackingState.off);
      expect(next.mount, initial.mount);
      expect(next.network, initial.network);
    });

    test('update network → NetworkState.hotspot, gps intact', () {
      final initial = _initial();
      final next = initial.applyUpdate(_update(
        kind: 'network',
        stateJson: {
          'state': 'hotspot',
          'details': {'ssid': 'AstroBrain-AP'},
          'since': '2026-04-17T20:35:00Z',
          'message': null,
        },
      ));
      expect(next.network.state, NetworkState.hotspot);
      expect(next.gps, initial.gps);
      expect(next.tracking, initial.tracking);
    });

    test('update system → SystemInfoState.warning, tracking intact', () {
      final initial = _initial();
      final next = initial.applyUpdate(_update(
        kind: 'system',
        stateJson: {
          'state': 'warning',
          'details': {'cpu_temp_c': 75.0},
          'since': '2026-04-17T20:35:00Z',
          'message': 'CPU chaud',
        },
        overall: 'orange',
      ));
      expect(next.system.state, SystemInfoState.warning);
      expect(next.tracking, initial.tracking);
      expect(next.mount, initial.mount);
    });

    test('update avec subsystem inconnu throws FormatException', () {
      final initial = _initial();
      expect(
        () => initial.applyUpdate(_update(
          kind: 'bogus',
          stateJson: {
            'state': 'whatever',
            'details': <String, dynamic>{},
            'since': '2026-04-17T20:35:00Z',
            'message': null,
          },
        )),
        throwsFormatException,
      );
    });
  });

  group('SystemState alignment subsystem', () {
    Map<String, dynamic> baseSubsystems() => {
          'mount': {
            'state': 'ready',
            'details': {},
            'since': '2026-05-31T20:00:00Z'
          },
          'gps': {
            'state': 'fix_3d',
            'details': {},
            'since': '2026-05-31T20:00:00Z'
          },
          'tracking': {
            'state': 'off',
            'details': {},
            'since': '2026-05-31T20:00:00Z'
          },
          'network': {
            'state': 'client',
            'details': {},
            'since': '2026-05-31T20:00:00Z'
          },
          'system': {
            'state': 'ok',
            'details': {},
            'since': '2026-05-31T20:00:00Z'
          },
        };

    test('parses alignment subsystem with is_aligned', () {
      final subs = baseSubsystems()
        ..['alignment'] = {
          'state': 'idle',
          'details': {'is_aligned': true},
          'since': '2026-05-31T20:00:00Z',
        };
      final s = SystemState.fromJson({
        'overall': 'blue',
        'subsystems': subs,
        'seq': 1,
        'ts': '2026-05-31T20:00:00Z',
      });
      expect(s.isAligned, isTrue);
    });

    test('isAligned false when alignment subsystem absent', () {
      final s = SystemState.fromJson({
        'overall': 'blue',
        'subsystems': baseSubsystems(),
        'seq': 1,
        'ts': '2026-05-31T20:00:00Z',
      });
      expect(s.isAligned, isFalse);
    });
  });
}
