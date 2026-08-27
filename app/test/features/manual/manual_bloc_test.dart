import 'package:astro_brain/features/manual/manual_bloc.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;

  setUpAll(() {
    registerFallbackValue(Axis.alt);
    registerFallbackValue(Direction.plus);
  });

  setUp(() {
    api = _MockApi();
    when(() => api.slew(
            axis: any(named: 'axis'),
            direction: any(named: 'direction'),
            rate: any(named: 'rate')))
        .thenAnswer((_) async {});
    when(() => api.stop(axis: any(named: 'axis'))).thenAnswer((_) async {});
    when(() => api.reconnectMount()).thenAnswer((_) async {});
  });

  blocTest<ManualBloc, ManualState>(
    'ManualRateChanged clampé entre 1 et 8 (le rate 9x n\'existe pas côté INDI)',
    build: () => ManualBloc(api: api),
    act: (b) => b
      ..add(const ManualRateChanged(12))
      ..add(const ManualRateChanged(0)),
    expect: () => [
      const ManualState(rate: 8),
      const ManualState(rate: 1),
    ],
  );

  blocTest<ManualBloc, ManualState>(
    'ManualSlewPressed appelle api.slew avec le rate courant',
    build: () => ManualBloc(api: api),
    act: (b) => b
      ..add(const ManualRateChanged(7))
      ..add(const ManualSlewPressed(axis: Axis.alt, direction: Direction.plus)),
    verify: (_) {
      verify(() => api.slew(
          axis: Axis.alt, direction: Direction.plus, rate: 7)).called(1);
    },
  );

  blocTest<ManualBloc, ManualState>(
    'ManualReconnectPressed appelle api.reconnectMount',
    build: () => ManualBloc(api: api),
    act: (b) => b.add(const ManualReconnectPressed()),
    verify: (_) {
      verify(() => api.reconnectMount()).called(1);
    },
  );

  blocTest<ManualBloc, ManualState>(
    'échec api.slew → lastError rempli',
    build: () {
      when(() => api.slew(
              axis: any(named: 'axis'),
              direction: any(named: 'direction'),
              rate: any(named: 'rate')))
          .thenThrow(ApiException('boom'));
      return ManualBloc(api: api);
    },
    act: (b) => b
        .add(const ManualSlewPressed(axis: Axis.alt, direction: Direction.plus)),
    expect: () => [
      isA<ManualState>().having((s) => s.lastError, 'lastError', contains('boom')),
    ],
  );
}
