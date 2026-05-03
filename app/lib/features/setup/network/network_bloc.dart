/// BLoC gérant la configuration réseau (host/port du Pi).
library;

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../../../services/pi_host.dart';
import 'network_event.dart';
import 'network_state.dart';

class NetworkBloc extends Bloc<NetworkEvent, NetworkState> {
  NetworkBloc({required SharedPreferences prefs, http.Client? httpClient})
      : _prefs = prefs,
        _http = httpClient ?? http.Client(),
        _ownsHttp = httpClient == null,
        super(_initialFromPrefs(prefs)) {
    on<NetworkLoaded>(_onLoaded);
    on<NetworkHostChanged>((e, emit) =>
        emit(state.copyWith(hostInput: e.host, testStatus: TestStatus.idle, testError: null)));
    on<NetworkPortChanged>((e, emit) =>
        emit(state.copyWith(portInput: e.port, testStatus: TestStatus.idle, testError: null)));
    on<NetworkTestRequested>(_onTest);
    on<NetworkSaveRequested>(_onSave);
    on<NetworkResetRequested>(_onReset);
  }

  final SharedPreferences _prefs;
  final http.Client _http;
  final bool _ownsHttp;

  static NetworkState _initialFromPrefs(SharedPreferences prefs) {
    final host = prefs.getString(PiHost.prefsHostKey) ?? 'astro-brain.local';
    final port = prefs.getInt(PiHost.prefsPortKey) ?? 8000;
    return NetworkState(
      hostInput: host,
      portInput: port,
      savedHost: host,
      savedPort: port,
    );
  }

  void _onLoaded(NetworkLoaded e, Emitter<NetworkState> emit) {
    emit(_initialFromPrefs(_prefs));
  }

  Future<void> _onTest(NetworkTestRequested e, Emitter<NetworkState> emit) async {
    emit(state.copyWith(testStatus: TestStatus.testing, testError: null));
    try {
      final uri = Uri.http('${state.hostInput}:${state.portInput}', '/state');
      final r = await _http.get(uri).timeout(const Duration(seconds: 3));
      if (r.statusCode == 200) {
        emit(state.copyWith(testStatus: TestStatus.ok, testError: null));
      } else {
        emit(state.copyWith(
          testStatus: TestStatus.error,
          testError: 'HTTP ${r.statusCode}',
        ));
      }
    } catch (err) {
      emit(state.copyWith(testStatus: TestStatus.error, testError: err.toString()));
    }
  }

  Future<void> _onSave(NetworkSaveRequested e, Emitter<NetworkState> emit) async {
    await _prefs.setString(PiHost.prefsHostKey, state.hostInput);
    await _prefs.setInt(PiHost.prefsPortKey, state.portInput);
    emit(state.copyWith(savedHost: state.hostInput, savedPort: state.portInput));
  }

  Future<void> _onReset(NetworkResetRequested e, Emitter<NetworkState> emit) async {
    await _prefs.remove(PiHost.prefsHostKey);
    await _prefs.remove(PiHost.prefsPortKey);
    emit(NetworkState.initial().copyWith(savedHost: null, savedPort: null));
  }

  @override
  Future<void> close() async {
    if (_ownsHttp) _http.close();
    return super.close();
  }
}
