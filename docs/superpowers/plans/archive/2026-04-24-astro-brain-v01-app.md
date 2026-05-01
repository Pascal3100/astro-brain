# Astro-Brain v0.1 — App Flutter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer l'app Flutter v0.1 sur téléphone Android : SplashScreen → HomeScreen (joystick + rate + tracking) + SystemScreen (diagnostic). Le backend FastAPI tourne déjà sur le Pi à `http://astro-brain:8000`.

**Architecture :**
- **Pattern BLoC / MVVM-like** via `flutter_bloc`. Un Bloc par domaine : `AppBloc` (état système consommé depuis le SSE), `HomeBloc` (commandes slew/stop/tracking), `SplashCubit` (séquence de connexion), `ThemeCubit` (déjà en place).
- **Services injectés via `RepositoryProvider`** (`ApiService` REST, `EventStreamService` SSE). Les Blocs les consomment via `context.read<T>()`.
- **Source unique de vérité côté app** : `AppBloc.state.system` est alimenté par les events SSE et exposé aux widgets via `BlocBuilder`. Zéro polling.
- **Structure feature-first** sous `lib/features/` (splash, home, system). Le thème reste dans `lib/theme/`. Les widgets partagés (`GlobalDot`, `HudPanel`) dans `lib/widgets/`.

**Tech Stack :** Flutter 3.41.6, Dart 3.11.4, `flutter_bloc ^9`, `equatable ^2`, `http ^1`, `google_fonts`, `phosphor_flutter`. Tests : `flutter_test`, `bloc_test`, `mocktail`, `shared_preferences` (persistance thème, en fin de plan).

**Référence spec :** `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md` (section « App Flutter — Téléphone »).

---

## File Structure

```
app/lib/
├── main.dart                                    # Point d'entrée (simplifié en Task 13)
├── app.dart                                     # Widget racine + router + providers
├── theme/                                       # DÉJÀ FAIT
│   ├── design_tokens.dart
│   ├── app_colors.dart
│   ├── app_typography.dart
│   ├── astro_theme.dart
│   └── theme_cubit.dart
├── models/
│   ├── subsystem_kind.dart                      # enum (mount | gps | tracking | network | system)
│   ├── subsystem_states.dart                    # enums MountState / GpsState / ... avec fromJson
│   ├── overall_status.dart                      # enum (green | blue | orange | red | offline)
│   ├── subsystem_state.dart                     # SubsystemState<T> data class
│   └── system_state.dart                        # SystemState agrégé
├── services/
│   ├── pi_host.dart                             # résolution host/port (défaut astro-brain.local:8000)
│   ├── api_service.dart                         # client REST (POST /slew /stop /tracking, GET /state)
│   ├── sse_event.dart                           # classe intermédiaire (event, data)
│   ├── sse_parser.dart                          # parser bas niveau text/event-stream
│   └── event_stream_service.dart                # client SSE avec reconnect + stream<SystemState>
├── state/
│   └── app_bloc/
│       ├── app_bloc.dart
│       ├── app_event.dart
│       └── app_state.dart
├── features/
│   ├── splash/
│   │   ├── splash_cubit.dart
│   │   ├── splash_state.dart
│   │   └── splash_screen.dart
│   ├── home/
│   │   ├── home_screen.dart
│   │   ├── home_bloc.dart
│   │   ├── home_event.dart
│   │   ├── home_state.dart
│   │   └── widgets/
│   │       ├── status_bar.dart
│   │       ├── dpad_control.dart
│   │       ├── rate_control.dart
│   │       └── tracking_toggle.dart
│   └── system/
│       ├── system_screen.dart
│       └── widgets/
│           └── subsystem_card.dart
└── widgets/
    ├── global_dot.dart                          # pastille colorée + halo glow
    └── hud_panel.dart                           # panneau avec bordure + fond tinté

app/test/
├── models/
│   ├── subsystem_states_test.dart
│   └── system_state_test.dart
├── services/
│   ├── sse_parser_test.dart
│   ├── api_service_test.dart
│   └── event_stream_service_test.dart
├── state/
│   └── app_bloc_test.dart
├── features/
│   ├── splash/splash_cubit_test.dart
│   ├── home/home_bloc_test.dart
│   └── home/widgets/dpad_control_test.dart
└── widget_test.dart                             # DÉJÀ FAIT (AppColors + ThemeCubit)
```

**Philosophie des fichiers :**
- Un enum = un fichier court. Un Bloc = 3 fichiers (bloc/event/state).
- Zéro `Color(0xFF…)` en dehors de `theme/design_tokens.dart`. Zéro `GoogleFonts.*` en dehors de `theme/app_typography.dart`.
- Les Blocs **ne connaissent pas `BuildContext`**. Ils reçoivent leurs services au `create:` du `BlocProvider`.
- Les widgets **ne connaissent pas les services**. Ils lisent `BlocBuilder` et émettent via `context.read<XxxBloc>().add(...)`.

---

## Task 1 — Modèles de données

**Files:**
- Create: `app/lib/models/subsystem_kind.dart`
- Create: `app/lib/models/subsystem_states.dart`
- Create: `app/lib/models/overall_status.dart`
- Create: `app/lib/models/subsystem_state.dart`
- Create: `app/lib/models/system_state.dart`
- Create: `app/test/models/subsystem_states_test.dart`
- Create: `app/test/models/system_state_test.dart`
- Modify: `app/pubspec.yaml` (ajout de `http` si pas déjà présent — il est déjà tiré transitivement par `google_fonts`, mais on le déclare explicitement)

- [ ] **Step 1.1 : Ajouter les dépendances manquantes**

```bash
cd app && flutter pub add http && flutter pub add --dev bloc_test mocktail
```

Vérifier que `pubspec.yaml` contient bien `http`, `bloc_test`, `mocktail`.

- [ ] **Step 1.2 : Écrire le test des enums (TDD — fail first)**

`app/test/models/subsystem_states_test.dart` :

```dart
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
  });

  group('TrackingState.fromJson', () {
    test('parse off / sidereal', () {
      expect(TrackingState.fromJson('off'), TrackingState.off);
      expect(TrackingState.fromJson('sidereal'), TrackingState.sidereal);
    });
  });

  group('NetworkState.fromJson', () {
    test('parse les 3 valeurs', () {
      expect(NetworkState.fromJson('offline'), NetworkState.offline);
      expect(NetworkState.fromJson('client'), NetworkState.client);
      expect(NetworkState.fromJson('hotspot'), NetworkState.hotspot);
    });
  });

  group('SystemInfoState.fromJson', () {
    test('parse ok / warning / critical', () {
      expect(SystemInfoState.fromJson('ok'), SystemInfoState.ok);
      expect(SystemInfoState.fromJson('warning'), SystemInfoState.warning);
      expect(SystemInfoState.fromJson('critical'), SystemInfoState.critical);
    });
  });
}
```

Run `flutter test test/models/subsystem_states_test.dart` → doit FAIL (fichier source absent).

- [ ] **Step 1.3 : Implémenter les enums**

`app/lib/models/subsystem_states.dart` :

```dart
/// Enums miroirs des états publiés par le backend (voir spec v0.1, section
/// « Modèle d'état système »). Chaque enum expose `fromJson(String)` qui
/// accepte la valeur snake_case du backend et jette `FormatException` sur
/// une valeur inconnue.

enum MountState { disconnected, connecting, ready, moving, error;
  static MountState fromJson(String v) => switch (v) {
        'disconnected' => MountState.disconnected,
        'connecting' => MountState.connecting,
        'ready' => MountState.ready,
        'moving' => MountState.moving,
        'error' => MountState.error,
        _ => throw FormatException('MountState inconnu: $v'),
      };
}

enum GpsState { off, noFix, searching, fix2d, fix3d;
  static GpsState fromJson(String v) => switch (v) {
        'off' => GpsState.off,
        'no_fix' => GpsState.noFix,
        'searching' => GpsState.searching,
        'fix_2d' => GpsState.fix2d,
        'fix_3d' => GpsState.fix3d,
        _ => throw FormatException('GpsState inconnu: $v'),
      };
}

enum TrackingState { off, sidereal;
  static TrackingState fromJson(String v) => switch (v) {
        'off' => TrackingState.off,
        'sidereal' => TrackingState.sidereal,
        _ => throw FormatException('TrackingState inconnu: $v'),
      };
}

enum NetworkState { offline, client, hotspot;
  static NetworkState fromJson(String v) => switch (v) {
        'offline' => NetworkState.offline,
        'client' => NetworkState.client,
        'hotspot' => NetworkState.hotspot,
        _ => throw FormatException('NetworkState inconnu: $v'),
      };
}

enum SystemInfoState { ok, warning, critical;
  static SystemInfoState fromJson(String v) => switch (v) {
        'ok' => SystemInfoState.ok,
        'warning' => SystemInfoState.warning,
        'critical' => SystemInfoState.critical,
        _ => throw FormatException('SystemInfoState inconnu: $v'),
      };
}
```

Run `flutter test test/models/subsystem_states_test.dart` → PASS.

- [ ] **Step 1.4 : Créer `SubsystemKind` et `OverallStatus`**

`app/lib/models/subsystem_kind.dart` :

```dart
/// Identifiant stable d'un sous-système dans l'état agrégé.
enum SubsystemKind {
  mount,
  gps,
  tracking,
  network,
  system;

  static SubsystemKind fromJson(String v) => values.firstWhere(
        (k) => k.name == v,
        orElse: () => throw FormatException('SubsystemKind inconnu: $v'),
      );
}
```

`app/lib/models/overall_status.dart` :

```dart
/// Statut global agrégé (spec v0.1 : règles 1→4 dans `overall`).
/// `offline` est un état CÔTÉ APP (Pi injoignable), pas émis par le backend.
enum OverallStatus { green, blue, orange, red, offline;
  static OverallStatus fromJson(String v) => switch (v) {
        'green' => OverallStatus.green,
        'blue' => OverallStatus.blue,
        'orange' => OverallStatus.orange,
        'red' => OverallStatus.red,
        _ => throw FormatException('OverallStatus inconnu: $v'),
      };
}
```

- [ ] **Step 1.5 : Écrire le test de `SystemState.fromJson`**

`app/test/models/system_state_test.dart` :

```dart
import 'dart:convert';

import 'package:astro_brain/models/overall_status.dart';
import 'package:astro_brain/models/subsystem_kind.dart';
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
      // Les autres subsystems sont intacts.
      expect(next.mount.state, MountState.ready);
    });
  });
}
```

Run → FAIL.

- [ ] **Step 1.6 : Implémenter `SubsystemState` et `SystemState`**

`app/lib/models/subsystem_state.dart` :

```dart
import 'package:equatable/equatable.dart';

/// Un sous-système porté par le backend : [state] (enum typé côté appelant),
/// [details] libres, [since] horodatage du dernier changement, [message]
/// optionnel pour erreurs ou infos humaines.
class SubsystemState<T> extends Equatable {
  const SubsystemState({
    required this.state,
    required this.details,
    required this.since,
    this.message,
  });

  final T state;
  final Map<String, dynamic> details;
  final DateTime since;
  final String? message;

  factory SubsystemState.fromJson(
    Map<String, dynamic> json,
    T Function(String) stateParser,
  ) {
    return SubsystemState<T>(
      state: stateParser(json['state'] as String),
      details: Map<String, dynamic>.from(
          (json['details'] as Map?) ?? const <String, dynamic>{}),
      since: DateTime.parse(json['since'] as String),
      message: json['message'] as String?,
    );
  }

  @override
  List<Object?> get props => [state, details, since, message];
}
```

`app/lib/models/system_state.dart` :

```dart
import 'package:equatable/equatable.dart';

import 'overall_status.dart';
import 'subsystem_kind.dart';
import 'subsystem_state.dart';
import 'subsystem_states.dart';

/// État agrégé de tout le système côté backend. Source unique de vérité
/// pour l'UI (alimentée par le snapshot initial + les events SSE `update`).
class SystemState extends Equatable {
  const SystemState({
    required this.overall,
    required this.mount,
    required this.gps,
    required this.tracking,
    required this.network,
    required this.system,
    required this.seq,
    required this.ts,
  });

  final OverallStatus overall;
  final SubsystemState<MountState> mount;
  final SubsystemState<GpsState> gps;
  final SubsystemState<TrackingState> tracking;
  final SubsystemState<NetworkState> network;
  final SubsystemState<SystemInfoState> system;
  final int seq;
  final DateTime ts;

  factory SystemState.fromJson(Map<String, dynamic> json) {
    final subs = json['subsystems'] as Map<String, dynamic>;
    return SystemState(
      overall: OverallStatus.fromJson(json['overall'] as String),
      mount: SubsystemState.fromJson(
          subs['mount'] as Map<String, dynamic>, MountState.fromJson),
      gps: SubsystemState.fromJson(
          subs['gps'] as Map<String, dynamic>, GpsState.fromJson),
      tracking: SubsystemState.fromJson(
          subs['tracking'] as Map<String, dynamic>, TrackingState.fromJson),
      network: SubsystemState.fromJson(
          subs['network'] as Map<String, dynamic>, NetworkState.fromJson),
      system: SubsystemState.fromJson(
          subs['system'] as Map<String, dynamic>, SystemInfoState.fromJson),
      seq: json['seq'] as int,
      ts: DateTime.parse(json['ts'] as String),
    );
  }

  /// Applique un event `update` SSE et renvoie une nouvelle [SystemState].
  /// Les autres sous-systèmes sont conservés.
  SystemState applyUpdate(Map<String, dynamic> update) {
    final kind = SubsystemKind.fromJson(update['subsystem'] as String);
    final stateJson = update['state'] as Map<String, dynamic>;
    final overall = OverallStatus.fromJson(update['overall'] as String);
    final seq = update['seq'] as int;
    final ts = DateTime.parse(update['ts'] as String);

    return SystemState(
      overall: overall,
      mount: kind == SubsystemKind.mount
          ? SubsystemState.fromJson(stateJson, MountState.fromJson)
          : mount,
      gps: kind == SubsystemKind.gps
          ? SubsystemState.fromJson(stateJson, GpsState.fromJson)
          : gps,
      tracking: kind == SubsystemKind.tracking
          ? SubsystemState.fromJson(stateJson, TrackingState.fromJson)
          : tracking,
      network: kind == SubsystemKind.network
          ? SubsystemState.fromJson(stateJson, NetworkState.fromJson)
          : network,
      system: kind == SubsystemKind.system
          ? SubsystemState.fromJson(stateJson, SystemInfoState.fromJson)
          : system,
      seq: seq,
      ts: ts,
    );
  }

  @override
  List<Object?> get props =>
      [overall, mount, gps, tracking, network, system, seq, ts];
}
```

Run `flutter test test/models/` → tous verts.

- [ ] **Step 1.7 : Commit**

```bash
git add app/lib/models app/test/models app/pubspec.yaml app/pubspec.lock
git commit -m "feat(app): modèles Dart pour SystemState + enums subsystèmes"
```

---

## Task 2 — Configuration hôte (`PiHost`)

**Files:**
- Create: `app/lib/services/pi_host.dart`

Trivial mais centralisé pour pouvoir, plus tard, exposer un écran de config manuelle.

- [ ] **Step 2.1 : Créer la classe**

`app/lib/services/pi_host.dart` :

```dart
/// Résolution de l'hôte du backend Astro-Brain.
///
/// Par défaut : `astro-brain.local:8000` (mDNS, résolvable sur le Wi-Fi local).
/// Quand on ajoutera un écran de config manuelle (hors v0.1), il devra
/// juste produire un [PiHost] différent et le passer au [RepositoryProvider]
/// racine — tout le reste reste inchangé.
class PiHost {
  const PiHost({this.host = 'astro-brain.local', this.port = 8000});

  final String host;
  final int port;

  Uri restUri(String path) => Uri.http('$host:$port', path);

  /// Les navigateurs / HttpClient mobiles gèrent bien SSE sur http:// local.
  /// TLS sera à considérer quand on sortira du réseau privé (hors v0.1).
  Uri sseUri(String path) => Uri.http('$host:$port', path);
}
```

- [ ] **Step 2.2 : Commit**

```bash
git add app/lib/services/pi_host.dart
git commit -m "feat(app): PiHost — résolution hôte backend centralisée"
```

---

## Task 3 — Parser SSE bas niveau

**Files:**
- Create: `app/lib/services/sse_event.dart`
- Create: `app/lib/services/sse_parser.dart`
- Create: `app/test/services/sse_parser_test.dart`

Le parser est pur fonction → ligne/octets bruts → `SseEvent`. Aucun I/O. Testable trivialement.

- [ ] **Step 3.1 : Écrire le test**

`app/test/services/sse_parser_test.dart` :

```dart
import 'package:astro_brain/services/sse_event.dart';
import 'package:astro_brain/services/sse_parser.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SseParser', () {
    test('parse un event simple terminé par ligne vide', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: snapshot\n');
      parser.feed('data: {"ok":true}\n');
      parser.feed('\n');
      expect(events, [SseEvent(event: 'snapshot', data: '{"ok":true}')]);
    });

    test('concatène plusieurs lignes data: séparées par \\n', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: update\ndata: {"a":1}\ndata: {"b":2}\n\n');
      expect(events.single.data, '{"a":1}\n{"b":2}');
    });

    test('ignore les lignes commentaires (ping `:`)', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed(': ping\n\n');
      parser.feed('event: foo\ndata: bar\n\n');
      expect(events, [SseEvent(event: 'foo', data: 'bar')]);
    });

    test('event sans type explicite → event="message"', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('data: hello\n\n');
      expect(events.single.event, 'message');
    });

    test('supporte les chunks coupés au milieu d\'une ligne', () {
      final events = <SseEvent>[];
      final parser = SseParser(events.add);
      parser.feed('event: up');
      parser.feed('date\ndata: x');
      parser.feed('\n\n');
      expect(events.single, SseEvent(event: 'update', data: 'x'));
    });
  });
}
```

Run → FAIL.

- [ ] **Step 3.2 : Implémenter `SseEvent`**

`app/lib/services/sse_event.dart` :

```dart
import 'package:equatable/equatable.dart';

class SseEvent extends Equatable {
  const SseEvent({required this.event, required this.data});
  final String event;
  final String data;

  @override
  List<Object> get props => [event, data];
}
```

- [ ] **Step 3.3 : Implémenter le parser**

`app/lib/services/sse_parser.dart` :

```dart
import 'sse_event.dart';

/// Parser text/event-stream conforme à la spec WHATWG (version minimale,
/// suffisante pour notre backend) : chaque bloc se termine par une ligne
/// vide ; `event:` définit le type, `data:` ajoute une ligne au buffer.
class SseParser {
  SseParser(this.onEvent);

  final void Function(SseEvent event) onEvent;
  final StringBuffer _lineBuf = StringBuffer();

  String? _eventType;
  final StringBuffer _dataBuf = StringBuffer();

  void feed(String chunk) {
    for (var i = 0; i < chunk.length; i++) {
      final c = chunk[i];
      if (c == '\n') {
        _processLine(_lineBuf.toString());
        _lineBuf.clear();
      } else if (c != '\r') {
        _lineBuf.write(c);
      }
    }
  }

  void _processLine(String line) {
    if (line.isEmpty) {
      _dispatch();
      return;
    }
    if (line.startsWith(':')) return; // commentaire / ping

    final colon = line.indexOf(':');
    final field = colon == -1 ? line : line.substring(0, colon);
    var value = colon == -1 ? '' : line.substring(colon + 1);
    if (value.startsWith(' ')) value = value.substring(1);

    switch (field) {
      case 'event':
        _eventType = value;
        break;
      case 'data':
        if (_dataBuf.isNotEmpty) _dataBuf.write('\n');
        _dataBuf.write(value);
        break;
      // `id:` et `retry:` ignorés en v0.1.
    }
  }

  void _dispatch() {
    if (_dataBuf.isEmpty && _eventType == null) return;
    onEvent(SseEvent(
      event: _eventType ?? 'message',
      data: _dataBuf.toString(),
    ));
    _eventType = null;
    _dataBuf.clear();
  }
}
```

Run → tous verts.

- [ ] **Step 3.4 : Commit**

```bash
git add app/lib/services/sse_event.dart app/lib/services/sse_parser.dart app/test/services/sse_parser_test.dart
git commit -m "feat(app): parser SSE bas niveau (ligne/chunks → SseEvent)"
```

---

## Task 4 — `ApiService` (REST)

**Files:**
- Create: `app/lib/services/api_service.dart`
- Create: `app/test/services/api_service_test.dart`

- [ ] **Step 4.1 : Écrire le test avec `http.MockClient`**

`app/test/services/api_service_test.dart` :

```dart
import 'dart:convert';

import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const host = PiHost(host: 'astro-brain.local', port: 8000);

  group('ApiService.fetchState', () {
    test('GET /state renvoie un SystemState parsé', () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/state');
        return http.Response(_snapshot, 200,
            headers: {'content-type': 'application/json'});
      });
      final api = ApiService(host: host, client: client);
      final state = await api.fetchState();
      expect(state.seq, 142);
    });

    test('jette ApiException sur status != 200', () async {
      final client = MockClient(
          (_) async => http.Response('oops', 500));
      final api = ApiService(host: host, client: client);
      expect(api.fetchState(), throwsA(isA<ApiException>()));
    });
  });

  group('ApiService.slew', () {
    test('POST /slew avec body JSON correct', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        expect(req.url.path, '/slew');
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.slew(axis: Axis.alt, direction: Direction.plus, rate: 5);
      expect(captured, {'axis': 'alt', 'direction': '+', 'rate': 5});
    });
  });

  group('ApiService.stop', () {
    test('POST /stop sans axis envoie body vide', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.stop();
      expect(captured, <String, dynamic>{});
    });

    test('POST /stop avec axis envoie le champ', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.stop(axis: Axis.az);
      expect(captured, {'axis': 'az'});
    });
  });

  group('ApiService.setTracking', () {
    test('POST /tracking { enabled: true }', () async {
      var captured = <String, dynamic>{};
      final client = MockClient((req) async {
        captured = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response('{"ok": true}', 200);
      });
      final api = ApiService(host: host, client: client);
      await api.setTracking(true);
      expect(captured, {'enabled': true});
    });
  });
}

const _snapshot = '''
{
  "overall": "green",
  "subsystems": {
    "mount": {"state": "ready", "details": {}, "since": "2026-04-17T20:31:12Z", "message": null},
    "gps": {"state": "fix_3d", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "tracking": {"state": "sidereal", "details": {}, "since": "2026-04-17T20:30:00Z", "message": null},
    "network": {"state": "client", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null},
    "system": {"state": "ok", "details": {}, "since": "2026-04-17T20:29:00Z", "message": null}
  },
  "seq": 142,
  "ts": "2026-04-17T20:31:12Z"
}
''';
```

Run → FAIL.

- [ ] **Step 4.2 : Implémenter `ApiService`**

`app/lib/services/api_service.dart` :

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/system_state.dart';
import 'pi_host.dart';

enum Axis { alt, az;
  String toJson() => name;
}

enum Direction { plus, minus;
  String toJson() => this == Direction.plus ? '+' : '-';
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Client REST vers le backend FastAPI. Un timeout court (3 s) sur toutes
/// les requêtes : l'UI doit savoir rapidement que le Pi est injoignable
/// pour afficher l'état offline.
class ApiService {
  ApiService({required this.host, http.Client? client})
      : _client = client ?? http.Client();

  final PiHost host;
  final http.Client _client;

  static const Duration _timeout = Duration(seconds: 3);

  Future<SystemState> fetchState() async {
    final resp = await _client.get(host.restUri('/state')).timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('GET /state failed',
          statusCode: resp.statusCode);
    }
    return SystemState.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<void> slew({
    required Axis axis,
    required Direction direction,
    required int rate,
  }) async {
    await _post('/slew', {
      'axis': axis.toJson(),
      'direction': direction.toJson(),
      'rate': rate,
    });
  }

  Future<void> stop({Axis? axis}) async {
    await _post('/stop', axis == null ? {} : {'axis': axis.toJson()});
  }

  Future<void> setTracking(bool enabled) async {
    await _post('/tracking', {'enabled': enabled});
  }

  Future<void> _post(String path, Map<String, dynamic> body) async {
    final resp = await _client
        .post(
          host.restUri(path),
          headers: const {'content-type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(_timeout);
    if (resp.statusCode != 200) {
      throw ApiException('POST $path failed',
          statusCode: resp.statusCode);
    }
  }

  void dispose() => _client.close();
}
```

Run → tous verts.

- [ ] **Step 4.3 : Commit**

```bash
git add app/lib/services/api_service.dart app/test/services/api_service_test.dart
git commit -m "feat(app): ApiService REST (slew, stop, tracking, fetchState)"
```

---

## Task 5 — `EventStreamService` (SSE + reconnexion)

**Files:**
- Create: `app/lib/services/event_stream_service.dart`
- Create: `app/test/services/event_stream_service_test.dart`

On utilise `http.Client().send(StreamedRequest)` pour obtenir un stream bytes → le parser de la Task 3 découpe en SseEvents → on les mappe en `SystemState` complet (snapshot remplace, update applique). Le stream exposé aux consommateurs reçoit **déjà** l'état complet.

Reconnexion : à chaque perte de connexion, on relance via un back-off exponentiel (1s, 2s, 4s, max 10s). Le serveur renvoie un `snapshot` à l'ouverture, donc pas de rattrapage applicatif.

- [ ] **Step 5.1 : Écrire le test (injection d'un `http.Client` mock qui livre le flux)**

`app/test/services/event_stream_service_test.dart` :

```dart
import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/overall_status.dart';
import 'package:astro_brain/models/subsystem_states.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

class _FakeClient extends http.BaseClient {
  _FakeClient(this.controller);
  final StreamController<List<int>> controller;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return http.StreamedResponse(
      controller.stream,
      200,
      headers: {'content-type': 'text/event-stream'},
    );
  }
}

const _snapshot = '''
{"overall":"green","subsystems":{"mount":{"state":"ready","details":{},"since":"2026-04-17T20:31:12Z","message":null},"gps":{"state":"fix_3d","details":{},"since":"2026-04-17T20:30:00Z","message":null},"tracking":{"state":"off","details":{},"since":"2026-04-17T20:30:00Z","message":null},"network":{"state":"client","details":{},"since":"2026-04-17T20:29:00Z","message":null},"system":{"state":"ok","details":{},"since":"2026-04-17T20:29:00Z","message":null}},"seq":1,"ts":"2026-04-17T20:31:12Z"}
''';

void main() {
  test('le snapshot initial est émis comme SystemState', () async {
    final bytes = StreamController<List<int>>();
    final svc = EventStreamService(
      host: const PiHost(),
      clientFactory: () => _FakeClient(bytes),
    );

    final first = svc.stream.first;
    svc.start();

    bytes.add(utf8.encode('event: snapshot\ndata: $_snapshot\n\n'));

    final state = await first.timeout(const Duration(seconds: 2));
    expect(state.seq, 1);
    expect(state.gps.state, GpsState.fix3d);

    await svc.stop();
    await bytes.close();
  });

  test('un event update applique le changement sur le snapshot courant',
      () async {
    final bytes = StreamController<List<int>>();
    final svc = EventStreamService(
      host: const PiHost(),
      clientFactory: () => _FakeClient(bytes),
    );

    final states = <SystemState>[];
    final sub = svc.stream.listen(states.add);
    svc.start();

    bytes.add(utf8.encode('event: snapshot\ndata: $_snapshot\n\n'));
    bytes.add(utf8.encode(
        'event: update\ndata: {"subsystem":"gps","state":{"state":"searching","details":{},"since":"2026-04-17T20:32:00Z","message":null},"overall":"orange","seq":2,"ts":"2026-04-17T20:32:00Z"}\n\n'));

    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(states.length, 2);
    expect(states[1].gps.state, GpsState.searching);
    expect(states[1].overall, OverallStatus.orange);

    await sub.cancel();
    await svc.stop();
    await bytes.close();
  });
}
```

Run → FAIL.

- [ ] **Step 5.2 : Implémenter `EventStreamService`**

`app/lib/services/event_stream_service.dart` :

```dart
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/system_state.dart';
import 'pi_host.dart';
import 'sse_event.dart';
import 'sse_parser.dart';

/// Service SSE qui maintient une connexion permanente vers `/events` et
/// expose un [stream] de [SystemState] complets.
///
/// - Au `snapshot` initial : émet directement l'état parsé.
/// - Sur `update` : applique le diff sur l'état courant, émet l'état complet.
/// - Sur déconnexion ou erreur : tente un reconnect avec back-off
///   exponentiel (1s, 2s, 4s, plafond 10s). Le serveur renverra un
///   nouveau `snapshot` à la reconnexion, donc pas de rattrapage
///   applicatif à faire.
class EventStreamService {
  EventStreamService({
    required this.host,
    http.Client Function()? clientFactory,
  }) : _clientFactory = clientFactory ?? http.Client.new;

  final PiHost host;
  final http.Client Function() _clientFactory;

  final StreamController<SystemState> _out =
      StreamController<SystemState>.broadcast();
  SystemState? _current;
  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Timer? _reconnectTimer;
  int _retryIndex = 0;
  bool _stopped = false;

  static const List<Duration> _backoff = [
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
    Duration(seconds: 10),
  ];

  Stream<SystemState> get stream => _out.stream;

  /// Démarre la connexion. Idempotent : un appel pendant qu'une connexion
  /// est déjà active ne fait rien.
  void start() {
    if (_stopped) return;
    _connect();
  }

  Future<void> stop() async {
    _stopped = true;
    _reconnectTimer?.cancel();
    await _sub?.cancel();
    _client?.close();
    await _out.close();
  }

  void _connect() {
    final client = _clientFactory();
    _client = client;
    final req = http.Request('GET', host.sseUri('/events'))
      ..headers['accept'] = 'text/event-stream';
    final parser = SseParser(_onEvent);

    client.send(req).then((resp) {
      if (resp.statusCode != 200) {
        _scheduleReconnect();
        return;
      }
      _retryIndex = 0;
      _sub = resp.stream.listen(
        (chunk) => parser.feed(utf8.decode(chunk, allowMalformed: true)),
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    }).catchError((_) => _scheduleReconnect());
  }

  void _onEvent(SseEvent event) {
    if (event.event == 'snapshot') {
      final json = jsonDecode(event.data) as Map<String, dynamic>;
      _current = SystemState.fromJson(json);
      _out.add(_current!);
    } else if (event.event == 'update') {
      final current = _current;
      if (current == null) return; // update avant snapshot : on ignore
      final json = jsonDecode(event.data) as Map<String, dynamic>;
      _current = current.applyUpdate(json);
      _out.add(_current!);
    }
  }

  void _scheduleReconnect() {
    if (_stopped) return;
    _sub?.cancel();
    _client?.close();
    _sub = null;
    _client = null;

    final delay = _backoff[_retryIndex.clamp(0, _backoff.length - 1)];
    _retryIndex++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, _connect);
  }
}
```

Run → tous verts.

- [ ] **Step 5.3 : Commit**

```bash
git add app/lib/services/event_stream_service.dart app/test/services/event_stream_service_test.dart
git commit -m "feat(app): EventStreamService SSE avec reconnect exponentiel"
```

---

## Task 6 — `AppBloc` (état global)

**Files:**
- Create: `app/lib/state/app_bloc/app_bloc.dart`
- Create: `app/lib/state/app_bloc/app_event.dart`
- Create: `app/lib/state/app_bloc/app_state.dart`
- Create: `app/test/state/app_bloc_test.dart`

Le Bloc s'abonne au `EventStreamService.stream` et expose l'état courant. Il expose aussi une notion d'**offline** quand la connexion n'a jamais été établie ou est perdue depuis trop longtemps (timeout de reconnect).

- [ ] **Step 6.1 : Définir les events et l'état**

`app/lib/state/app_bloc/app_event.dart` :

```dart
import 'package:equatable/equatable.dart';

import '../../models/system_state.dart';

sealed class AppEvent extends Equatable {
  const AppEvent();
  @override
  List<Object?> get props => const [];
}

/// Émis au `initState` du widget racine — démarre le service SSE.
class AppStarted extends AppEvent {
  const AppStarted();
}

/// Émis en interne quand le service SSE livre un nouvel état.
class AppSystemStateReceived extends AppEvent {
  const AppSystemStateReceived(this.systemState);
  final SystemState systemState;
  @override
  List<Object> get props => [systemState];
}

/// Émis en interne quand le service SSE tombe en erreur.
class AppConnectionLost extends AppEvent {
  const AppConnectionLost();
}
```

`app/lib/state/app_bloc/app_state.dart` :

```dart
import 'package:equatable/equatable.dart';

import '../../models/overall_status.dart';
import '../../models/system_state.dart';

enum ConnectionStatus { connecting, connected, offline }

class AppState extends Equatable {
  const AppState({
    required this.connection,
    this.system,
  });

  const AppState.initial()
      : connection = ConnectionStatus.connecting,
        system = null;

  final ConnectionStatus connection;
  final SystemState? system;

  /// `overall` effectif côté UI : offline l'emporte sur les règles backend.
  OverallStatus get effectiveOverall => connection == ConnectionStatus.offline
      ? OverallStatus.offline
      : system?.overall ?? OverallStatus.blue;

  AppState copyWith({ConnectionStatus? connection, SystemState? system}) {
    return AppState(
      connection: connection ?? this.connection,
      system: system ?? this.system,
    );
  }

  @override
  List<Object?> get props => [connection, system];
}
```

- [ ] **Step 6.2 : Écrire le test**

`app/test/state/app_bloc_test.dart` :

```dart
import 'dart:async';
import 'dart:convert';

import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/state/app_bloc/app_event.dart';
import 'package:astro_brain/state/app_bloc/app_state.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockStream extends Mock implements EventStreamService {}

SystemState _sample() => SystemState.fromJson(jsonDecode(_snapshotJson));

const _snapshotJson = '''
{"overall":"green","subsystems":{"mount":{"state":"ready","details":{},"since":"2026-04-17T20:31:12Z","message":null},"gps":{"state":"fix_3d","details":{},"since":"2026-04-17T20:30:00Z","message":null},"tracking":{"state":"off","details":{},"since":"2026-04-17T20:30:00Z","message":null},"network":{"state":"client","details":{},"since":"2026-04-17T20:29:00Z","message":null},"system":{"state":"ok","details":{},"since":"2026-04-17T20:29:00Z","message":null}},"seq":1,"ts":"2026-04-17T20:31:12Z"}
''';

void main() {
  late StreamController<SystemState> controller;
  late _MockStream svc;

  setUp(() {
    controller = StreamController<SystemState>.broadcast();
    svc = _MockStream();
    when(() => svc.stream).thenAnswer((_) => controller.stream);
    when(() => svc.start()).thenAnswer((_) {});
    when(() => svc.stop()).thenAnswer((_) async {});
  });

  tearDown(() => controller.close());

  blocTest<AppBloc, AppState>(
    'AppStarted connecte le service et passe à connected au premier SystemState',
    build: () => AppBloc(eventStream: svc),
    act: (bloc) async {
      bloc.add(const AppStarted());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      controller.add(_sample());
    },
    wait: const Duration(milliseconds: 50),
    verify: (bloc) {
      expect(bloc.state.connection, ConnectionStatus.connected);
      expect(bloc.state.system?.seq, 1);
      verify(() => svc.start()).called(1);
    },
  );

  blocTest<AppBloc, AppState>(
    'AppConnectionLost repasse en offline',
    build: () => AppBloc(eventStream: svc),
    act: (bloc) async {
      bloc.add(const AppStarted());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      controller.add(_sample());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      bloc.add(const AppConnectionLost());
    },
    wait: const Duration(milliseconds: 50),
    verify: (bloc) {
      expect(bloc.state.connection, ConnectionStatus.offline);
    },
  );
}
```

- [ ] **Step 6.3 : Implémenter `AppBloc`**

`app/lib/state/app_bloc/app_bloc.dart` :

```dart
import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/event_stream_service.dart';
import 'app_event.dart';
import 'app_state.dart';

export 'app_event.dart';
export 'app_state.dart';

class AppBloc extends Bloc<AppEvent, AppState> {
  AppBloc({required EventStreamService eventStream})
      : _eventStream = eventStream,
        super(const AppState.initial()) {
    on<AppStarted>(_onStarted);
    on<AppSystemStateReceived>(_onSystemStateReceived);
    on<AppConnectionLost>(_onConnectionLost);
  }

  final EventStreamService _eventStream;
  StreamSubscription<Object>? _sub;

  Future<void> _onStarted(AppStarted e, Emitter<AppState> emit) async {
    _sub?.cancel();
    _sub = _eventStream.stream.listen(
      (sys) => add(AppSystemStateReceived(sys)),
      onError: (_) => add(const AppConnectionLost()),
    );
    _eventStream.start();
  }

  void _onSystemStateReceived(
      AppSystemStateReceived e, Emitter<AppState> emit) {
    emit(state.copyWith(
      connection: ConnectionStatus.connected,
      system: e.systemState,
    ));
  }

  void _onConnectionLost(AppConnectionLost e, Emitter<AppState> emit) {
    emit(state.copyWith(connection: ConnectionStatus.offline));
  }

  @override
  Future<void> close() async {
    await _sub?.cancel();
    await _eventStream.stop();
    return super.close();
  }
}
```

Run `flutter test test/state` → verts.

- [ ] **Step 6.4 : Commit**

```bash
git add app/lib/state/app_bloc app/test/state
git commit -m "feat(app): AppBloc — état global alimenté par SSE, gestion offline"
```

---

## Task 7 — Widgets partagés : `GlobalDot` + `HudPanel`

**Files:**
- Create: `app/lib/widgets/global_dot.dart`
- Create: `app/lib/widgets/hud_panel.dart`

- [ ] **Step 7.1 : Implémenter `GlobalDot`**

`app/lib/widgets/global_dot.dart` :

```dart
import 'package:flutter/material.dart';

import '../models/overall_status.dart';
import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

/// Pastille colorée + halo glow. En mode `OverallStatus.blue` (transition),
/// elle clignote à 1 Hz (fade-in/out). En offline, rouge saturé fixe.
class GlobalDot extends StatefulWidget {
  const GlobalDot({
    super.key,
    required this.status,
    this.size = DesignTokens.statusDotSize,
  });

  final OverallStatus status;
  final double size;

  @override
  State<GlobalDot> createState() => _GlobalDotState();
}

class _GlobalDotState extends State<GlobalDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  Color _color(AppColors colors) => switch (widget.status) {
        OverallStatus.green => colors.dotOk,
        OverallStatus.blue => colors.dotTransition,
        OverallStatus.orange => colors.dotWarn,
        OverallStatus.red => colors.dotError,
        OverallStatus.offline => colors.dotError,
      };

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final color = _color(colors);
    final pulsing = widget.status == OverallStatus.blue;

    Widget dot(double opacity) => Container(
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            color: color.withValues(alpha: opacity),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: opacity * 0.8),
                blurRadius: widget.size,
                spreadRadius: 0,
              ),
            ],
          ),
        );

    if (!pulsing) return dot(1.0);
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, __) => dot(0.45 + 0.55 * _pulse.value),
    );
  }
}
```

- [ ] **Step 7.2 : Implémenter `HudPanel`**

`app/lib/widgets/hud_panel.dart` :

```dart
import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/design_tokens.dart';

/// Panneau HUD : fond légèrement tinté d'accent, bordure fine colorée.
/// Base visuelle des cards, du D-Pad, de la status bar.
class HudPanel extends StatelessWidget {
  const HudPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(DesignTokens.spaceLG),
    this.radius = DesignTokens.radiusLG,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Color.lerp(colors.bgGradientTop, colors.accent, 0.04),
        border: Border.all(
          color: colors.accent.withValues(alpha: 0.2),
          width: DesignTokens.strokeThin,
        ),
        borderRadius: BorderRadius.circular(radius),
      ),
      child: child,
    );
  }
}
```

- [ ] **Step 7.3 : Commit**

```bash
git add app/lib/widgets
git commit -m "feat(app): widgets partagés GlobalDot (pulse bleu) + HudPanel"
```

---

## Task 8 — `SplashScreen` + `SplashCubit`

**Files:**
- Create: `app/lib/features/splash/splash_state.dart`
- Create: `app/lib/features/splash/splash_cubit.dart`
- Create: `app/lib/features/splash/splash_screen.dart`
- Create: `app/test/features/splash/splash_cubit_test.dart`

Le cubit orchestre les 3 phases (voir spec). En cas d'échec, expose un état d'erreur avec action `retry` ou `continueOffline`.

- [ ] **Step 8.1 : État + cubit**

`app/lib/features/splash/splash_state.dart` :

```dart
import 'package:equatable/equatable.dart';

enum SplashPhase { contacting, loading, openingStream, success, failure }

class SplashState extends Equatable {
  const SplashState({required this.phase, this.errorMessage});
  const SplashState.initial() : this(phase: SplashPhase.contacting);

  final SplashPhase phase;
  final String? errorMessage;

  SplashState copyWith({SplashPhase? phase, String? errorMessage}) =>
      SplashState(
        phase: phase ?? this.phase,
        errorMessage: errorMessage,
      );

  @override
  List<Object?> get props => [phase, errorMessage];
}
```

`app/lib/features/splash/splash_cubit.dart` :

```dart
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import '../../state/app_bloc/app_bloc.dart';
import 'splash_state.dart';

class SplashCubit extends Cubit<SplashState> {
  SplashCubit({required this.api, required this.appBloc})
      : super(const SplashState.initial());

  final ApiService api;
  final AppBloc appBloc;

  Future<void> start() async {
    emit(state.copyWith(phase: SplashPhase.contacting));
    try {
      await api.fetchState(); // ping + charge initial
      emit(state.copyWith(phase: SplashPhase.loading));
      // L'AppBloc gère le SSE ensuite ; on marque juste la phase.
      emit(state.copyWith(phase: SplashPhase.openingStream));
      appBloc.add(const AppStarted());
      emit(state.copyWith(phase: SplashPhase.success));
    } on Exception catch (e) {
      emit(state.copyWith(
        phase: SplashPhase.failure,
        errorMessage: e.toString(),
      ));
    }
  }

  /// Entre dans l'app en mode offline sans ouvrir la connexion SSE.
  /// L'AppBloc reste en `ConnectionStatus.connecting` tant qu'on n'a pas
  /// tenté un retry.
  void continueOffline() {
    emit(state.copyWith(phase: SplashPhase.success));
  }
}
```

- [ ] **Step 8.2 : Test du cubit (simple, fonctionnel)**

`app/test/features/splash/splash_cubit_test.dart` :

```dart
import 'dart:async';

import 'package:astro_brain/features/splash/splash_cubit.dart';
import 'package:astro_brain/features/splash/splash_state.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}
class _MockStream extends Mock implements EventStreamService {}
class _FakeSystemState extends Fake implements SystemState {}

void main() {
  setUpAll(() => registerFallbackValue(_FakeSystemState()));

  late _MockApi api;
  late _MockStream svc;
  late AppBloc appBloc;

  setUp(() {
    api = _MockApi();
    svc = _MockStream();
    when(() => svc.stream)
        .thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => svc.start()).thenAnswer((_) {});
    when(() => svc.stop()).thenAnswer((_) async {});
    appBloc = AppBloc(eventStream: svc);
  });

  tearDown(() => appBloc.close());

  blocTest<SplashCubit, SplashState>(
    'parcours nominal : contacting → loading → openingStream → success',
    build: () {
      when(() => api.fetchState()).thenAnswer((_) async => _FakeSystemState());
      return SplashCubit(api: api, appBloc: appBloc);
    },
    act: (c) => c.start(),
    expect: () => [
      const SplashState(phase: SplashPhase.contacting),
      const SplashState(phase: SplashPhase.loading),
      const SplashState(phase: SplashPhase.openingStream),
      const SplashState(phase: SplashPhase.success),
    ],
  );

  blocTest<SplashCubit, SplashState>(
    'échec du fetch → phase failure avec message',
    build: () {
      when(() => api.fetchState())
          .thenThrow(ApiException('boom', statusCode: 500));
      return SplashCubit(api: api, appBloc: appBloc);
    },
    act: (c) => c.start(),
    expect: () => [
      const SplashState(phase: SplashPhase.contacting),
      isA<SplashState>()
          .having((s) => s.phase, 'phase', SplashPhase.failure)
          .having((s) => s.errorMessage, 'errorMessage', contains('boom')),
    ],
  );
}
```

Run `flutter test test/features/splash` → verts.

- [ ] **Step 8.3 : Implémenter la view**

`app/lib/features/splash/splash_screen.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import 'splash_cubit.dart';
import 'splash_state.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.onReady});
  final VoidCallback onReady;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<SplashCubit>().start();
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return Scaffold(
      body: BlocListener<SplashCubit, SplashState>(
        listener: (ctx, state) {
          if (state.phase == SplashPhase.success) widget.onReady();
        },
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [colors.bgGradientTop, colors.bgGradientBottom],
            ),
          ),
          child: SafeArea(
            child: BlocBuilder<SplashCubit, SplashState>(
              builder: (ctx, state) {
                final failed = state.phase == SplashPhase.failure;
                return Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      failed
                          ? PhosphorIconsBold.warning
                          : PhosphorIconsBold.telescope,
                      size: DesignTokens.iconSizeXL * 2,
                      color: failed ? colors.dotError : colors.accent,
                    ),
                    const SizedBox(height: DesignTokens.spaceXL),
                    Text('ASTRO-BRAIN V 0.1', style: text.hudLabel),
                    const SizedBox(height: DesignTokens.space2XL),
                    _Step(label: 'CONTACTING ASTRO-BRAIN.LOCAL',
                        state: _stepStatus(state, SplashPhase.contacting)),
                    _Step(label: 'LOADING STATE SNAPSHOT',
                        state: _stepStatus(state, SplashPhase.loading)),
                    _Step(label: 'OPENING EVENT STREAM',
                        state: _stepStatus(state, SplashPhase.openingStream)),
                    if (failed) ...[
                      const SizedBox(height: DesignTokens.space2XL),
                      Text('ASTRO-BRAIN NOT REACHABLE',
                          style: text.hudValue
                              .copyWith(color: colors.dotError)),
                      const SizedBox(height: DesignTokens.spaceLG),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          FilledButton(
                            onPressed: () => ctx.read<SplashCubit>().start(),
                            child: const Text('RETRY'),
                          ),
                          const SizedBox(width: DesignTokens.spaceMD),
                          TextButton(
                            onPressed: () =>
                                ctx.read<SplashCubit>().continueOffline(),
                            child: const Text('CONTINUE OFFLINE →'),
                          ),
                        ],
                      ),
                    ],
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  _StepState _stepStatus(SplashState s, SplashPhase p) {
    if (s.phase == SplashPhase.failure) {
      return s.phase.index > p.index ? _StepState.done : _StepState.error;
    }
    if (s.phase.index > p.index || s.phase == SplashPhase.success) {
      return _StepState.done;
    }
    if (s.phase == p) return _StepState.active;
    return _StepState.pending;
  }
}

enum _StepState { pending, active, done, error }

class _Step extends StatelessWidget {
  const _Step({required this.label, required this.state});
  final String label;
  final _StepState state;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final icon = switch (state) {
      _StepState.pending => PhosphorIconsRegular.circle,
      _StepState.active => PhosphorIconsBold.circleDashed,
      _StepState.done => PhosphorIconsBold.check,
      _StepState.error => PhosphorIconsBold.x,
    };
    final color = switch (state) {
      _StepState.pending => colors.textMuted,
      _StepState.active => colors.accent,
      _StepState.done => colors.accent,
      _StepState.error => colors.dotError,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: DesignTokens.spaceXS),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          PhosphorIcon(icon, color: color, size: DesignTokens.iconSizeSM),
          const SizedBox(width: DesignTokens.spaceSM),
          Text(label, style: text.hudCaption.copyWith(color: color)),
        ],
      ),
    );
  }
}
```

- [ ] **Step 8.4 : Commit**

```bash
git add app/lib/features/splash app/test/features/splash
git commit -m "feat(app): SplashScreen + SplashCubit (3 phases + fallback offline)"
```

---

## Task 9 — `StatusBar` widget

**Files:**
- Create: `app/lib/features/home/widgets/status_bar.dart`

- [ ] **Step 9.1 : Implémentation**

`app/lib/features/home/widgets/status_bar.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../theme/theme_cubit.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

class StatusBar extends StatelessWidget {
  const StatusBar({super.key, required this.onOpenSystem});
  final VoidCallback onOpenSystem;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;

    return BlocBuilder<AppBloc, AppState>(
      builder: (ctx, state) {
        final overall = state.effectiveOverall;
        final mode = ctx.watch<ThemeCubit>().state;
        return HudPanel(
          padding: const EdgeInsets.symmetric(
            horizontal: DesignTokens.spaceLG,
            vertical: DesignTokens.spaceMD,
          ),
          child: Row(
            children: [
              InkWell(
                onTap: onOpenSystem,
                borderRadius: BorderRadius.circular(DesignTokens.radiusPill),
                child: Padding(
                  padding: const EdgeInsets.all(DesignTokens.spaceSM),
                  child: Row(
                    children: [
                      GlobalDot(status: overall,
                          size: DesignTokens.statusDotSizeLg),
                      const SizedBox(width: DesignTokens.spaceMD),
                      Text(overall.name.toUpperCase(), style: text.hudLabel),
                    ],
                  ),
                ),
              ),
              const Spacer(),
              IconButton(
                tooltip: mode == AstroThemeMode.day
                    ? 'Passer en mode nuit'
                    : 'Passer en mode jour',
                icon: PhosphorIcon(
                  mode == AstroThemeMode.day
                      ? PhosphorIconsBold.moon
                      : PhosphorIconsBold.sun,
                  color: colors.accent,
                ),
                onPressed: () => ctx.read<ThemeCubit>().toggle(),
              ),
            ],
          ),
        );
      },
    );
  }
}
```

- [ ] **Step 9.2 : Commit**

```bash
git add app/lib/features/home/widgets/status_bar.dart
git commit -m "feat(app): StatusBar (pastille + toggle thème)"
```

---

## Task 10 — `DPadControl` + `HomeBloc`

**Files:**
- Create: `app/lib/features/home/home_event.dart`
- Create: `app/lib/features/home/home_state.dart`
- Create: `app/lib/features/home/home_bloc.dart`
- Create: `app/lib/features/home/widgets/dpad_control.dart`
- Create: `app/test/features/home/home_bloc_test.dart`

Le DPad déclenche `slew` au press et `stop` au release. On garde le rate et le tracking dans `HomeState` local.

- [ ] **Step 10.1 : Events + state**

`app/lib/features/home/home_event.dart` :

```dart
import 'package:equatable/equatable.dart';

import '../../services/api_service.dart';

sealed class HomeEvent extends Equatable {
  const HomeEvent();
  @override
  List<Object?> get props => const [];
}

class HomeRateChanged extends HomeEvent {
  const HomeRateChanged(this.rate);
  final int rate;
  @override
  List<Object> get props => [rate];
}

class HomeSlewPressed extends HomeEvent {
  const HomeSlewPressed({required this.axis, required this.direction});
  final Axis axis;
  final Direction direction;
  @override
  List<Object> get props => [axis, direction];
}

class HomeSlewReleased extends HomeEvent {
  const HomeSlewReleased(this.axis);
  final Axis axis;
  @override
  List<Object> get props => [axis];
}

class HomeTrackingToggled extends HomeEvent {
  const HomeTrackingToggled(this.enabled);
  final bool enabled;
  @override
  List<Object> get props => [enabled];
}
```

`app/lib/features/home/home_state.dart` :

```dart
import 'package:equatable/equatable.dart';

class HomeState extends Equatable {
  const HomeState({this.rate = 5, this.lastError});
  final int rate;
  final String? lastError;

  HomeState copyWith({int? rate, String? lastError, bool clearError = false}) =>
      HomeState(
        rate: rate ?? this.rate,
        lastError: clearError ? null : (lastError ?? this.lastError),
      );

  @override
  List<Object?> get props => [rate, lastError];
}
```

- [ ] **Step 10.2 : Bloc**

`app/lib/features/home/home_bloc.dart` :

```dart
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/api_service.dart';
import 'home_event.dart';
import 'home_state.dart';

export 'home_event.dart';
export 'home_state.dart';

class HomeBloc extends Bloc<HomeEvent, HomeState> {
  HomeBloc({required this.api}) : super(const HomeState()) {
    on<HomeRateChanged>((e, emit) =>
        emit(state.copyWith(rate: e.rate.clamp(1, 9))));
    on<HomeSlewPressed>(_onSlew);
    on<HomeSlewReleased>(_onStop);
    on<HomeTrackingToggled>(_onTracking);
  }

  final ApiService api;

  Future<void> _onSlew(HomeSlewPressed e, Emitter<HomeState> emit) async {
    try {
      await api.slew(axis: e.axis, direction: e.direction, rate: state.rate);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onStop(HomeSlewReleased e, Emitter<HomeState> emit) async {
    try {
      await api.stop(axis: e.axis);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }

  Future<void> _onTracking(
      HomeTrackingToggled e, Emitter<HomeState> emit) async {
    try {
      await api.setTracking(e.enabled);
      emit(state.copyWith(clearError: true));
    } on Exception catch (err) {
      emit(state.copyWith(lastError: err.toString()));
    }
  }
}
```

- [ ] **Step 10.3 : Tests**

`app/test/features/home/home_bloc_test.dart` :

```dart
import 'package:astro_brain/features/home/home_bloc.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;

  setUp(() {
    api = _MockApi();
    when(() => api.slew(
            axis: any(named: 'axis'),
            direction: any(named: 'direction'),
            rate: any(named: 'rate')))
        .thenAnswer((_) async {});
    when(() => api.stop(axis: any(named: 'axis'))).thenAnswer((_) async {});
    when(() => api.setTracking(any())).thenAnswer((_) async {});
  });

  blocTest<HomeBloc, HomeState>(
    'HomeRateChanged clampé entre 1 et 9',
    build: () => HomeBloc(api: api),
    act: (b) => b
      ..add(const HomeRateChanged(12))
      ..add(const HomeRateChanged(0)),
    expect: () => [
      const HomeState(rate: 9),
      const HomeState(rate: 1),
    ],
  );

  blocTest<HomeBloc, HomeState>(
    'HomeSlewPressed appelle api.slew avec le rate courant',
    build: () => HomeBloc(api: api),
    act: (b) => b
      ..add(const HomeRateChanged(7))
      ..add(const HomeSlewPressed(axis: Axis.alt, direction: Direction.plus)),
    verify: (_) {
      verify(() => api.slew(
          axis: Axis.alt, direction: Direction.plus, rate: 7)).called(1);
    },
  );

  blocTest<HomeBloc, HomeState>(
    'échec api.slew → lastError rempli',
    build: () {
      when(() => api.slew(
              axis: any(named: 'axis'),
              direction: any(named: 'direction'),
              rate: any(named: 'rate')))
          .thenThrow(ApiException('boom'));
      return HomeBloc(api: api);
    },
    act: (b) => b
        .add(const HomeSlewPressed(axis: Axis.alt, direction: Direction.plus)),
    expect: () => [
      isA<HomeState>().having((s) => s.lastError, 'lastError', contains('boom')),
    ],
  );
}
```

Run → verts.

- [ ] **Step 10.4 : Widget `DPadControl`**

`app/lib/features/home/widgets/dpad_control.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../services/api_service.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/design_tokens.dart';
import '../home_bloc.dart';

class DPadControl extends StatelessWidget {
  const DPadControl({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) => a.connection != b.connection,
      builder: (ctx, app) {
        final disabled = app.connection != ConnectionStatus.connected;
        return Opacity(
          opacity: disabled ? 0.35 : 1,
          child: IgnorePointer(
            ignoring: disabled,
            child: GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              mainAxisSpacing: DesignTokens.spaceMD,
              crossAxisSpacing: DesignTokens.spaceMD,
              children: [
                const SizedBox(),
                _Btn(icon: PhosphorIconsBold.caretUp,
                    axis: Axis.alt, direction: Direction.plus),
                const SizedBox(),
                _Btn(icon: PhosphorIconsBold.caretLeft,
                    axis: Axis.az, direction: Direction.minus),
                const SizedBox(),
                _Btn(icon: PhosphorIconsBold.caretRight,
                    axis: Axis.az, direction: Direction.plus),
                const SizedBox(),
                _Btn(icon: PhosphorIconsBold.caretDown,
                    axis: Axis.alt, direction: Direction.minus),
                const SizedBox(),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Btn extends StatelessWidget {
  const _Btn({required this.icon, required this.axis, required this.direction});
  final IconData icon;
  final Axis axis;
  final Direction direction;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return GestureDetector(
      onTapDown: (_) => context
          .read<HomeBloc>()
          .add(HomeSlewPressed(axis: axis, direction: direction)),
      onTapUp: (_) =>
          context.read<HomeBloc>().add(HomeSlewReleased(axis)),
      onTapCancel: () =>
          context.read<HomeBloc>().add(HomeSlewReleased(axis)),
      child: Container(
        decoration: BoxDecoration(
          color: Color.lerp(colors.bgGradientTop, colors.accent, 0.08),
          border: Border.all(
            color: colors.accent.withValues(alpha: 0.4),
            width: DesignTokens.strokeRegular,
          ),
          borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
        ),
        child: Center(
          child: PhosphorIcon(icon,
              color: colors.accent, size: DesignTokens.iconSizeXL),
        ),
      ),
    );
  }
}
```

- [ ] **Step 10.5 : Commit**

```bash
git add app/lib/features/home app/test/features/home
git commit -m "feat(app): HomeBloc + DPadControl (slew on press, stop on release)"
```

---

## Task 11 — `RateControl` + `TrackingToggle`

**Files:**
- Create: `app/lib/features/home/widgets/rate_control.dart`
- Create: `app/lib/features/home/widgets/tracking_toggle.dart`

- [ ] **Step 11.1 : RateControl**

`app/lib/features/home/widgets/rate_control.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../home_bloc.dart';

class RateControl extends StatelessWidget {
  const RateControl({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<HomeBloc, HomeState>(
      buildWhen: (a, b) => a.rate != b.rate,
      builder: (ctx, state) {
        return Row(
          children: [
            IconButton(
              onPressed: () =>
                  ctx.read<HomeBloc>().add(HomeRateChanged(state.rate - 1)),
              icon: PhosphorIcon(PhosphorIconsBold.minus,
                  color: colors.accent),
            ),
            Expanded(
              child: Row(
                children: List.generate(9, (i) {
                  final n = i + 1;
                  final active = n <= state.rate;
                  return Expanded(
                    child: Container(
                      margin: const EdgeInsets.symmetric(
                          horizontal: DesignTokens.spaceXXS),
                      height: DesignTokens.spaceLG,
                      decoration: BoxDecoration(
                        color: active
                            ? colors.accent
                            : colors.accent.withValues(alpha: 0.15),
                        borderRadius:
                            BorderRadius.circular(DesignTokens.radiusSM),
                      ),
                    ),
                  );
                }),
              ),
            ),
            IconButton(
              onPressed: () =>
                  ctx.read<HomeBloc>().add(HomeRateChanged(state.rate + 1)),
              icon: PhosphorIcon(PhosphorIconsBold.plus,
                  color: colors.accent),
            ),
            SizedBox(
              width: 28,
              child: Text('${state.rate}',
                  textAlign: TextAlign.center, style: text.hudValue),
            ),
          ],
        );
      },
    );
  }
}
```

- [ ] **Step 11.2 : TrackingToggle**

`app/lib/features/home/widgets/tracking_toggle.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/subsystem_states.dart';
import '../../../state/app_bloc/app_bloc.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/hud_panel.dart';
import '../home_bloc.dart';

class TrackingToggle extends StatelessWidget {
  const TrackingToggle({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return BlocBuilder<AppBloc, AppState>(
      buildWhen: (a, b) =>
          a.connection != b.connection ||
          a.system?.tracking.state != b.system?.tracking.state,
      builder: (ctx, state) {
        final disabled = state.connection != ConnectionStatus.connected;
        final enabled = state.system?.tracking.state == TrackingState.sidereal;
        return Opacity(
          opacity: disabled ? 0.35 : 1,
          child: IgnorePointer(
            ignoring: disabled,
            child: HudPanel(
              child: Row(
                children: [
                  PhosphorIcon(PhosphorIconsBold.crosshairSimple,
                      color: enabled ? colors.accent : colors.textMuted),
                  const SizedBox(width: DesignTokens.spaceMD),
                  Expanded(
                    child: Text(
                      enabled ? 'TRACKING SIDEREAL' : 'TRACKING OFF',
                      style: text.hudValue.copyWith(
                        color: enabled ? colors.accent : colors.textMuted,
                      ),
                    ),
                  ),
                  Switch(
                    value: enabled,
                    onChanged: (v) =>
                        ctx.read<HomeBloc>().add(HomeTrackingToggled(v)),
                    activeThumbColor: colors.accent,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
```

- [ ] **Step 11.3 : Commit**

```bash
git add app/lib/features/home/widgets
git commit -m "feat(app): RateControl + TrackingToggle"
```

---

## Task 12 — `HomeScreen` (assemblage)

**Files:**
- Create: `app/lib/features/home/home_screen.dart`

- [ ] **Step 12.1 : Assembler les widgets**

`app/lib/features/home/home_screen.dart` :

```dart
import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/design_tokens.dart';
import 'widgets/dpad_control.dart';
import 'widgets/rate_control.dart';
import 'widgets/status_bar.dart';
import 'widgets/tracking_toggle.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.onOpenSystem});
  final VoidCallback onOpenSystem;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(DesignTokens.spaceLG),
            child: Column(
              children: [
                StatusBar(onOpenSystem: onOpenSystem),
                const SizedBox(height: DesignTokens.space2XL),
                const Expanded(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: DPadControl(),
                    ),
                  ),
                ),
                const SizedBox(height: DesignTokens.spaceXL),
                const RateControl(),
                const SizedBox(height: DesignTokens.spaceXL),
                const TrackingToggle(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 12.2 : Commit**

```bash
git add app/lib/features/home/home_screen.dart
git commit -m "feat(app): HomeScreen assemble StatusBar + DPad + Rate + Tracking"
```

---

## Task 13 — `SystemScreen` + `SubsystemCard`

**Files:**
- Create: `app/lib/features/system/widgets/subsystem_card.dart`
- Create: `app/lib/features/system/system_screen.dart`

- [ ] **Step 13.1 : `SubsystemCard`**

`app/lib/features/system/widgets/subsystem_card.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../models/overall_status.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/global_dot.dart';
import '../../../widgets/hud_panel.dart';

class SubsystemCard extends StatelessWidget {
  const SubsystemCard({
    super.key,
    required this.label,
    required this.icon,
    required this.stateLabel,
    required this.detailsText,
    required this.since,
    required this.dotStatus,
    this.message,
  });

  final String label;
  final IconData icon;
  final String stateLabel;
  final String detailsText;
  final DateTime since;
  final OverallStatus dotStatus;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    final agoSeconds = DateTime.now().difference(since).inSeconds;
    return HudPanel(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PhosphorIcon(icon,
              color: colors.accent, size: DesignTokens.iconSizeLG),
          const SizedBox(width: DesignTokens.spaceLG),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(label, style: text.hudLabel),
                    const Spacer(),
                    GlobalDot(status: dotStatus),
                  ],
                ),
                const SizedBox(height: DesignTokens.spaceXS),
                Text(stateLabel, style: text.hudValue),
                if (detailsText.isNotEmpty) ...[
                  const SizedBox(height: DesignTokens.spaceXS),
                  Text(detailsText, style: text.hudCaption),
                ],
                const SizedBox(height: DesignTokens.spaceXS),
                Text('depuis ${_formatAgo(agoSeconds)}',
                    style: text.hudCaption
                        .copyWith(color: colors.textMuted)),
                if (message != null) ...[
                  const SizedBox(height: DesignTokens.spaceSM),
                  Text(message!,
                      style:
                          text.hudCaption.copyWith(color: colors.dotError)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatAgo(int seconds) {
    if (seconds < 60) return '${seconds}s';
    if (seconds < 3600) return '${seconds ~/ 60}min';
    return '${seconds ~/ 3600}h';
  }
}
```

- [ ] **Step 13.2 : `SystemScreen`**

`app/lib/features/system/system_screen.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../models/overall_status.dart';
import '../../models/subsystem_state.dart';
import '../../models/subsystem_states.dart';
import '../../models/system_state.dart';
import '../../state/app_bloc/app_bloc.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_typography.dart';
import '../../theme/design_tokens.dart';
import 'widgets/subsystem_card.dart';

class SystemScreen extends StatelessWidget {
  const SystemScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: PhosphorIcon(PhosphorIconsBold.caretLeft, color: colors.accent),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text('SYSTEM', style: text.hudLabel.copyWith(fontSize: 13)),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: BlocBuilder<AppBloc, AppState>(
          builder: (ctx, state) {
            final sys = state.system;
            if (sys == null) {
              return Center(
                child: Text('NO STATE', style: text.hudLabel),
              );
            }
            return ListView(
              padding: const EdgeInsets.all(DesignTokens.spaceLG),
              children: [
                SubsystemCard(
                  label: 'MOUNT',
                  icon: PhosphorIconsBold.arrowsOutCardinal,
                  stateLabel: sys.mount.state.name.toUpperCase(),
                  detailsText: _mountDetails(sys.mount),
                  since: sys.mount.since,
                  dotStatus: _mountDot(sys.mount.state),
                  message: sys.mount.message,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'GPS',
                  icon: PhosphorIconsBold.gpsFix,
                  stateLabel: sys.gps.state.name.toUpperCase(),
                  detailsText: _gpsDetails(sys.gps),
                  since: sys.gps.since,
                  dotStatus: _gpsDot(sys.gps.state),
                  message: sys.gps.message,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'TRACKING',
                  icon: PhosphorIconsBold.crosshairSimple,
                  stateLabel: sys.tracking.state.name.toUpperCase(),
                  detailsText: '',
                  since: sys.tracking.since,
                  dotStatus: sys.tracking.state == TrackingState.sidereal
                      ? OverallStatus.green
                      : OverallStatus.orange,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'NETWORK',
                  icon: PhosphorIconsBold.wifiHigh,
                  stateLabel: sys.network.state.name.toUpperCase(),
                  detailsText: _networkDetails(sys.network),
                  since: sys.network.since,
                  dotStatus: sys.network.state == NetworkState.offline
                      ? OverallStatus.orange
                      : OverallStatus.green,
                ),
                const SizedBox(height: DesignTokens.spaceLG),
                SubsystemCard(
                  label: 'SYSTEM',
                  icon: sys.system.state == SystemInfoState.ok
                      ? PhosphorIconsBold.cpu
                      : PhosphorIconsBold.thermometerSimple,
                  stateLabel: sys.system.state.name.toUpperCase(),
                  detailsText: _systemDetails(sys.system),
                  since: sys.system.since,
                  dotStatus: switch (sys.system.state) {
                    SystemInfoState.ok => OverallStatus.green,
                    SystemInfoState.warning => OverallStatus.orange,
                    SystemInfoState.critical => OverallStatus.red,
                  },
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  String _mountDetails(SubsystemState<MountState> s) {
    final fw = s.details['firmware_version'];
    return fw == null ? '' : 'firmware $fw';
  }

  String _gpsDetails(SubsystemState<GpsState> s) {
    final lat = s.details['lat'];
    final lon = s.details['lon'];
    final sats = s.details['satellites'];
    if (lat == null || lon == null) return 'sats=${sats ?? 0}';
    return '${(lat as num).toStringAsFixed(4)} / ${(lon as num).toStringAsFixed(4)} · $sats sats';
  }

  String _networkDetails(SubsystemState<NetworkState> s) {
    final ssid = s.details['ssid'];
    final ip = s.details['ip'];
    if (ssid == null && ip == null) return '';
    return '$ssid · $ip';
  }

  String _systemDetails(SubsystemState<SystemInfoState> s) {
    final t = s.details['cpu_temp_c'];
    final load = s.details['cpu_load'];
    return '${t}°C · load $load';
  }

  OverallStatus _mountDot(MountState s) => switch (s) {
        MountState.ready || MountState.moving => OverallStatus.green,
        MountState.connecting => OverallStatus.blue,
        MountState.disconnected || MountState.error => OverallStatus.red,
      };

  OverallStatus _gpsDot(GpsState s) => switch (s) {
        GpsState.fix3d || GpsState.fix2d => OverallStatus.green,
        GpsState.searching => OverallStatus.blue,
        GpsState.off || GpsState.noFix => OverallStatus.orange,
      };
}
```

- [ ] **Step 13.3 : Commit**

```bash
git add app/lib/features/system
git commit -m "feat(app): SystemScreen + SubsystemCard (diagnostic 5 sous-systèmes)"
```

---

## Task 14 — Racine `app.dart` + routing + providers

**Files:**
- Create: `app/lib/app.dart`
- Modify: `app/lib/main.dart`

- [ ] **Step 14.1 : Créer `AstroBrainApp`**

`app/lib/app.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'features/home/home_bloc.dart';
import 'features/home/home_screen.dart';
import 'features/splash/splash_cubit.dart';
import 'features/splash/splash_screen.dart';
import 'features/system/system_screen.dart';
import 'services/api_service.dart';
import 'services/event_stream_service.dart';
import 'services/pi_host.dart';
import 'state/app_bloc/app_bloc.dart';
import 'theme/astro_theme.dart';
import 'theme/theme_cubit.dart';

class AstroBrainApp extends StatelessWidget {
  const AstroBrainApp({super.key});

  @override
  Widget build(BuildContext context) {
    const host = PiHost();

    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider<PiHost>.value(value: host),
        RepositoryProvider<ApiService>(
          create: (_) => ApiService(host: host),
          dispose: (s) => s.dispose(),
        ),
        RepositoryProvider<EventStreamService>(
          create: (_) => EventStreamService(host: host),
          dispose: (s) => s.stop(),
        ),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider<ThemeCubit>(create: (_) => ThemeCubit()),
          BlocProvider<AppBloc>(
            create: (ctx) => AppBloc(
              eventStream: ctx.read<EventStreamService>(),
            ),
          ),
          BlocProvider<HomeBloc>(
            create: (ctx) => HomeBloc(api: ctx.read<ApiService>()),
          ),
        ],
        child: BlocBuilder<ThemeCubit, AstroThemeMode>(
          builder: (ctx, mode) {
            return MaterialApp(
              title: 'Astro-Brain',
              debugShowCheckedModeBanner: false,
              theme: AstroTheme.buildDay(),
              darkTheme: AstroTheme.buildNight(),
              themeMode: mode == AstroThemeMode.day
                  ? ThemeMode.light
                  : ThemeMode.dark,
              home: _RootRouter(),
            );
          },
        ),
      ),
    );
  }
}

class _RootRouter extends StatefulWidget {
  @override
  State<_RootRouter> createState() => _RootRouterState();
}

class _RootRouterState extends State<_RootRouter> {
  bool _ready = false;

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return BlocProvider<SplashCubit>(
        create: (ctx) => SplashCubit(
          api: ctx.read<ApiService>(),
          appBloc: ctx.read<AppBloc>(),
        ),
        child: SplashScreen(onReady: () => setState(() => _ready = true)),
      );
    }
    return HomeScreen(
      onOpenSystem: () {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const SystemScreen()),
        );
      },
    );
  }
}
```

- [ ] **Step 14.2 : Simplifier `main.dart`**

`app/lib/main.dart` :

```dart
import 'package:flutter/material.dart';

import 'app.dart';

void main() {
  runApp(const AstroBrainApp());
}
```

- [ ] **Step 14.3 : `flutter analyze` et vérification complète**

```bash
cd app && flutter analyze && flutter test
```

Attendu : `No issues found.` + tous les tests verts.

- [ ] **Step 14.4 : Smoke test sur téléphone**

Avec le téléphone branché (ADB actif) :

```bash
cd app && flutter run
```

Checks manuels :
1. Splash s'affiche et passe les 3 étapes → HomeScreen.
2. Pastille globale en haut à gauche est verte (si backend OK sur `astro-brain.local:8000`).
3. Tap sur la pastille ouvre SystemScreen avec les 5 cartes.
4. Caret-back revient sur HomeScreen.
5. Boutons du D-Pad déclenchent des logs dans `journalctl -u astro-brain.service -f` côté Pi (slew puis stop).
6. Toggle tracking change l'état SSE (icône switch + pastille verte).
7. Icône lune/soleil bascule le thème.
8. Débranche le câble réseau du Pi : la pastille bascule en `offline`, D-Pad devient grisé.

- [ ] **Step 14.5 : Commit**

```bash
git add app/lib/app.dart app/lib/main.dart
git commit -m "feat(app): racine AstroBrainApp avec MultiProvider + routing SplashScreen → Home"
```

---

## Task 15 — Persistance du thème (shared_preferences)

**Files:**
- Modify: `app/pubspec.yaml`
- Modify: `app/lib/theme/theme_cubit.dart`
- Modify: `app/lib/app.dart`

- [ ] **Step 15.1 : Ajouter `shared_preferences`**

```bash
cd app && flutter pub add shared_preferences
```

- [ ] **Step 15.2 : Hydrater le cubit**

Remplacer `app/lib/theme/theme_cubit.dart` :

```dart
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum AstroThemeMode { day, night }

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
```

- [ ] **Step 15.3 : Initialiser dans `main.dart`**

`app/lib/main.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  runApp(AstroBrainApp(prefs: prefs));
}
```

- [ ] **Step 15.4 : Propager dans `AstroBrainApp`**

Dans `app/lib/app.dart`, changer la signature et la construction du `ThemeCubit` :

```dart
class AstroBrainApp extends StatelessWidget {
  const AstroBrainApp({super.key, required this.prefs});
  final SharedPreferences prefs;

  @override
  Widget build(BuildContext context) {
    // ...existing MultiRepositoryProvider...
    // dans MultiBlocProvider :
    BlocProvider<ThemeCubit>(create: (_) => ThemeCubit(prefs: prefs)),
    // ...
  }
}
```

(Ajouter `import 'package:shared_preferences/shared_preferences.dart';` en tête.)

- [ ] **Step 15.5 : Vérifier**

```bash
cd app && flutter analyze && flutter test
```

Smoke test téléphone : bascule en mode nuit, `q` pour tuer l'app, relance → on revient directement en nuit.

- [ ] **Step 15.6 : Commit**

```bash
git add app/lib/theme/theme_cubit.dart app/lib/main.dart app/lib/app.dart app/pubspec.yaml app/pubspec.lock
git commit -m "feat(app): persistance du thème via shared_preferences"
```

---

## Task 16 — Reconnect manuel depuis l'app

**Files:**
- Modify: `app/lib/state/app_bloc/app_event.dart`
- Modify: `app/lib/state/app_bloc/app_bloc.dart`
- Modify: `app/lib/features/home/widgets/status_bar.dart`

Quand l'AppBloc est en `offline`, exposer un bouton "reconnecter" (icône `arrowClockwise`) dans la status bar qui relance le service SSE.

- [ ] **Step 16.1 : Event**

Ajouter dans `app_event.dart` :

```dart
class AppReconnectRequested extends AppEvent {
  const AppReconnectRequested();
}
```

- [ ] **Step 16.2 : Handler dans `AppBloc`**

Dans `app_bloc.dart`, enregistrer le handler et la logique :

```dart
on<AppReconnectRequested>(_onReconnect);

Future<void> _onReconnect(
    AppReconnectRequested e, Emitter<AppState> emit) async {
  emit(state.copyWith(connection: ConnectionStatus.connecting));
  await _sub?.cancel();
  _sub = _eventStream.stream.listen(
    (sys) => add(AppSystemStateReceived(sys)),
    onError: (_) => add(const AppConnectionLost()),
  );
  // `EventStreamService.start()` est idempotent côté implémentation —
  // si déjà en train de retenter, on déclenche un reset propre :
  await _eventStream.stop();
  _eventStream.start();
}
```

Note : pour pouvoir appeler `start()` après `stop()`, `EventStreamService` doit redevenir réutilisable. Ajuster dans `event_stream_service.dart` :

```dart
// Remplacer le champ _stopped par un flag rearmable :
bool get _closed => _out.isClosed;

// Dans stop(), NE PLUS fermer _out, juste couper la connexion courante :
Future<void> stop() async {
  _reconnectTimer?.cancel();
  await _sub?.cancel();
  _client?.close();
  _sub = null;
  _client = null;
}

// Et un vrai dispose() pour la fin de vie :
Future<void> dispose() async {
  await stop();
  await _out.close();
}
```

Appeler `dispose()` (et non `stop()`) dans `RepositoryProvider.dispose` de `AstroBrainApp` et dans `AppBloc.close()`.

- [ ] **Step 16.3 : UI dans `StatusBar`**

Ajouter dans `status_bar.dart` (avant le `IconButton` lune/soleil) :

```dart
if (state.connection == ConnectionStatus.offline)
  IconButton(
    tooltip: 'Reconnecter au Pi',
    icon: PhosphorIcon(PhosphorIconsBold.arrowClockwise,
        color: colors.accent),
    onPressed: () => ctx.read<AppBloc>().add(const AppReconnectRequested()),
  ),
```

- [ ] **Step 16.4 : Vérifications**

`flutter analyze` + `flutter test`.

Smoke test : débrancher le réseau du Pi → pastille offline → icône reconnect apparaît → rebrancher → tap reconnect → re-vert.

- [ ] **Step 16.5 : Commit**

```bash
git add app/lib/state app/lib/services/event_stream_service.dart app/lib/features/home/widgets/status_bar.dart
git commit -m "feat(app): bouton de reconnexion manuelle quand offline"
```

---

## Task 17 — Mise à jour du journal et clôture du plan

**Files:**
- Modify: `docs/journal.md`

- [ ] **Step 17.1 : Ajouter une session « app v0.1 livrée »**

Dans `docs/journal.md`, après la Session 8, ajouter une entrée qui résume :
- Les 3 écrans livrés (Splash, Home, System).
- Les Blocs / Cubits créés (`AppBloc`, `HomeBloc`, `SplashCubit`, `ThemeCubit`).
- Les services (`ApiService`, `EventStreamService`, `SseParser`).
- Le test de bout en bout sur téléphone.
- Ce qu'il reste hors scope v0.1 (config manuelle d'IP, mode hotspot côté Pi, mDNS fallback).

Mettre à jour la section **État du projet** : `v0.1 app Flutter livrée — parité joystick + tracking avec la raquette Celestron via téléphone`.

- [ ] **Step 17.2 : Commit**

```bash
git add docs/journal.md
git commit -m "docs(journal): v0.1 app Flutter livrée"
```

---

## Self-Review

- **Spec coverage** : chaque point de la section « App Flutter — Téléphone » de la spec est couvert :
  - Splash 3 phases + fallback offline → Task 8
  - HomeScreen (DPad, rate, tracking) → Tasks 10-12
  - SystemScreen 5 cartes → Task 13
  - Modèle d'état unifié → Task 1
  - Reconnexion SSE avec back-off exp → Task 5
  - Throttling client : absent (c'est côté serveur, déjà fait)
  - Mode offline (grisage + `OFFLINE` dans la pastille + bouton reconnect) → Tasks 6, 9, 16
  - mDNS `astro-brain.local:8000` → Task 2
  - Thème jour/nuit, toggle lune/soleil, jamais de bleu/vert la nuit → déjà fait + Task 9 + Task 15
  - Icônes Phosphor → utilisées partout
- **Placeholders** : aucune phrase "TBD", "TODO", "implement later". Chaque step montre le code.
- **Type consistency** : `Axis`, `Direction`, `MountState`, etc. sont définis une fois (Tasks 1 et 4) et réutilisés. `SystemState.applyUpdate` retourne `SystemState` (Task 1) et est bien consommé par `EventStreamService` (Task 5) puis par `AppBloc` (Task 6). `EventStreamService.start() / stop() / dispose()` — après Task 16, la forme finale est : `start()`, `stop()`, `dispose()` (3 méthodes). Les `RepositoryProvider.dispose` appellent `dispose()`, pas `stop()`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-24-astro-brain-v01-app.md`. Deux options d'exécution :

1. **Subagent-Driven (recommandé)** — Je dispatche un subagent frais par tâche, revue entre chaque, itération rapide.
2. **Inline Execution** — On déroule les tâches dans cette session avec checkpoints de revue.

**Laquelle tu préfères ?**
