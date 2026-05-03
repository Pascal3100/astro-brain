import 'package:equatable/equatable.dart';

enum TestStatus { idle, testing, ok, error }

class NetworkState extends Equatable {
  const NetworkState({
    required this.hostInput,
    required this.portInput,
    this.testStatus = TestStatus.idle,
    this.testError,
    this.savedHost,
    this.savedPort,
  });

  factory NetworkState.initial() =>
      const NetworkState(hostInput: 'astro-brain.local', portInput: 8000);

  final String hostInput;
  final int portInput;
  final TestStatus testStatus;
  final String? testError;
  final String? savedHost;
  final int? savedPort;

  bool get dirty => savedHost != hostInput || savedPort != portInput;

  NetworkState copyWith({
    String? hostInput,
    int? portInput,
    TestStatus? testStatus,
    Object? testError = _sentinel,
    String? savedHost,
    int? savedPort,
  }) =>
      NetworkState(
        hostInput: hostInput ?? this.hostInput,
        portInput: portInput ?? this.portInput,
        testStatus: testStatus ?? this.testStatus,
        testError: identical(testError, _sentinel) ? this.testError : testError as String?,
        savedHost: savedHost ?? this.savedHost,
        savedPort: savedPort ?? this.savedPort,
      );

  @override
  List<Object?> get props =>
      [hostInput, portInput, testStatus, testError, savedHost, savedPort];
}

const _sentinel = Object();
