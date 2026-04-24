import 'package:astro_brain/features/home/home_bloc.dart';
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
