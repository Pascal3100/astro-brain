import 'package:astro_brain/features/setup/network/network_bloc.dart';
import 'package:astro_brain/features/setup/network/network_event.dart';
import 'package:astro_brain/features/setup/network/network_state.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

late SharedPreferences _prefs;

http.Client _fakeOk() => MockClient((_) async => http.Response('{}', 200));
http.Client _fakeFail() => MockClient((_) async => http.Response('nope', 500));

void main() {
  setUp(() => SharedPreferences.setMockInitialValues(<String, Object>{}));

  blocTest<NetworkBloc, NetworkState>(
    'load → defaults when prefs empty',
    build: () => NetworkBloc(prefs: _prefs, httpClient: _fakeOk()),
    setUp: () async => _prefs = await SharedPreferences.getInstance(),
    act: (b) => b.add(const NetworkLoaded()),
    expect: () => [
      isA<NetworkState>()
          .having((s) => s.hostInput, 'host', 'astro-brain.local')
          .having((s) => s.portInput, 'port', 8000)
          .having((s) => s.savedHost, 'savedHost', 'astro-brain.local'),
    ],
  );

  blocTest<NetworkBloc, NetworkState>(
    'test ok then save persists to prefs',
    build: () => NetworkBloc(prefs: _prefs, httpClient: _fakeOk()),
    setUp: () async => _prefs = await SharedPreferences.getInstance(),
    act: (b) async {
      b.add(const NetworkLoaded());
      await Future.delayed(Duration.zero);
      b.add(const NetworkHostChanged('192.168.1.42'));
      b.add(const NetworkPortChanged(9000));
      b.add(const NetworkTestRequested());
      await Future.delayed(const Duration(milliseconds: 100));
      b.add(const NetworkSaveRequested());
    },
    verify: (_) async {
      expect(_prefs.getString(PiHost.prefsHostKey), '192.168.1.42');
      expect(_prefs.getInt(PiHost.prefsPortKey), 9000);
    },
  );

  blocTest<NetworkBloc, NetworkState>(
    'test failure sets status to error',
    build: () => NetworkBloc(prefs: _prefs, httpClient: _fakeFail()),
    setUp: () async => _prefs = await SharedPreferences.getInstance(),
    act: (b) async {
      b.add(const NetworkLoaded());
      await Future.delayed(Duration.zero);
      b.add(const NetworkTestRequested());
    },
    skip: 1,
    expect: () => [
      isA<NetworkState>().having((s) => s.testStatus, 'status', TestStatus.testing),
      isA<NetworkState>().having((s) => s.testStatus, 'status', TestStatus.error),
    ],
  );

  blocTest<NetworkBloc, NetworkState>(
    'reset clears prefs and reverts to defaults',
    build: () => NetworkBloc(prefs: _prefs, httpClient: _fakeOk()),
    setUp: () async {
      SharedPreferences.setMockInitialValues({
        'astro.host': '10.0.0.1',
        'astro.port': 7000,
      });
      _prefs = await SharedPreferences.getInstance();
    },
    act: (b) {
      b.add(const NetworkLoaded());
      b.add(const NetworkResetRequested());
    },
    verify: (_) async {
      expect(_prefs.getString(PiHost.prefsHostKey), isNull);
      expect(_prefs.getInt(PiHost.prefsPortKey), isNull);
    },
  );
}
