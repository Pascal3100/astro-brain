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
