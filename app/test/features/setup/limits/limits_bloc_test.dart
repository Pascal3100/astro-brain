import 'package:astro_brain/features/setup/limits/limits_bloc.dart';
import 'package:astro_brain/features/setup/limits/limits_event.dart';
import 'package:astro_brain/features/setup/limits/limits_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

ApiService _apiWith(MockClientHandler handler) =>
    ApiService(host: const PiHost(), client: MockClient(handler));

void main() {
  group('LimitsAltBloc — Reloaded', () {
    blocTest<LimitsAltBloc, LimitsAltState>(
      '404 → état vide (lower/upper null), pas d\'erreur',
      build: () => LimitsAltBloc(
        api: _apiWith((req) async => http.Response('not found', 404)),
      ),
      act: (bloc) => bloc.add(const LimitsAltReloaded()),
      verify: (bloc) {
        expect(bloc.state.isLoading, isFalse);
        expect(bloc.state.lowerDeg, isNull);
        expect(bloc.state.upperDeg, isNull);
        expect(bloc.state.errorMessage, isNull);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      '200 avec limites → pré-remplit lower/upper',
      build: () => LimitsAltBloc(
        api: _apiWith(
          (req) async => http.Response(
            '{"min_deg": -5.0, "max_deg": 87.0}',
            200,
          ),
        ),
      ),
      act: (bloc) => bloc.add(const LimitsAltReloaded()),
      verify: (bloc) {
        expect(bloc.state.lowerDeg, -5.0);
        expect(bloc.state.upperDeg, 87.0);
        expect(bloc.state.canSave, isTrue);
      },
    );
  });

  group('LimitsAltBloc — captures', () {
    blocTest<LimitsAltBloc, LimitsAltState>(
      'lower puis upper : canSave true quand écart >= 30',
      build: () => LimitsAltBloc(
        api: _apiWith((_) async => http.Response('not found', 404)),
      ),
      act: (bloc) {
        bloc.add(const LimitsAltLowerCaptured(-3.2));
        bloc.add(const LimitsAltUpperCaptured(85.0));
      },
      verify: (bloc) {
        expect(bloc.state.lowerDeg, -3.2);
        expect(bloc.state.upperDeg, 85.0);
        expect(bloc.state.canSave, isTrue);
        expect(bloc.state.hasRangeWarning, isFalse);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      'upper puis lower (ordre inverse) : même résultat',
      build: () => LimitsAltBloc(
        api: _apiWith((_) async => http.Response('not found', 404)),
      ),
      act: (bloc) {
        bloc.add(const LimitsAltUpperCaptured(80.0));
        bloc.add(const LimitsAltLowerCaptured(-2.0));
      },
      verify: (bloc) {
        expect(bloc.state.lowerDeg, -2.0);
        expect(bloc.state.upperDeg, 80.0);
        expect(bloc.state.canSave, isTrue);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      'écart < 30 : warning visible, canSave false',
      build: () => LimitsAltBloc(
        api: _apiWith((_) async => http.Response('not found', 404)),
      ),
      act: (bloc) {
        bloc.add(const LimitsAltLowerCaptured(10.0));
        bloc.add(const LimitsAltUpperCaptured(35.0));
      },
      verify: (bloc) {
        expect(bloc.state.canSave, isFalse);
        expect(bloc.state.hasRangeWarning, isTrue);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      're-capture lower : écrase la valeur SANS reset upper',
      build: () => LimitsAltBloc(
        api: _apiWith((_) async => http.Response('not found', 404)),
      ),
      act: (bloc) {
        bloc.add(const LimitsAltLowerCaptured(-5.0));
        bloc.add(const LimitsAltUpperCaptured(85.0));
        bloc.add(const LimitsAltLowerCaptured(-2.5));
      },
      verify: (bloc) {
        expect(bloc.state.lowerDeg, -2.5);
        expect(bloc.state.upperDeg, 85.0);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      'capture après save : reset isSaved',
      build: () => LimitsAltBloc(
        api: _apiWith((req) async {
          if (req.method == 'PUT') {
            return http.Response('{"min_deg": -5.0, "max_deg": 85.0}', 200);
          }
          return http.Response('not found', 404);
        }),
      ),
      act: (bloc) async {
        bloc.add(const LimitsAltLowerCaptured(-5.0));
        bloc.add(const LimitsAltUpperCaptured(85.0));
        bloc.add(const LimitsAltSaveRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        expect(bloc.state.isSaved, isTrue);
        bloc.add(const LimitsAltLowerCaptured(-3.0));
      },
      verify: (bloc) {
        expect(bloc.state.isSaved, isFalse);
        expect(bloc.state.lowerDeg, -3.0);
      },
    );
  });

  group('LimitsAltBloc — SaveRequested', () {
    blocTest<LimitsAltBloc, LimitsAltState>(
      'happy path : PUT 200 → isSaved=true',
      build: () => LimitsAltBloc(
        api: _apiWith((req) async {
          expect(req.method, 'PUT');
          expect(req.url.path, '/limits/alt');
          return http.Response('{"min_deg": -3.2, "max_deg": 87.0}', 200);
        }),
      ),
      act: (bloc) async {
        bloc.add(const LimitsAltLowerCaptured(-3.2));
        bloc.add(const LimitsAltUpperCaptured(87.0));
        bloc.add(const LimitsAltSaveRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.isSaving, isFalse);
        expect(bloc.state.isSaved, isTrue);
        expect(bloc.state.errorMessage, isNull);
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      '422 → errorMessage explicite, isSaved reste false',
      build: () => LimitsAltBloc(
        api: _apiWith(
          (req) async => http.Response('{"detail": "invalid"}', 422),
        ),
      ),
      act: (bloc) async {
        bloc.add(const LimitsAltLowerCaptured(0.0));
        bloc.add(const LimitsAltUpperCaptured(40.0));
        bloc.add(const LimitsAltSaveRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.isSaving, isFalse);
        expect(bloc.state.isSaved, isFalse);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.errorMessage, contains('Plage'));
      },
    );

    blocTest<LimitsAltBloc, LimitsAltState>(
      'save sans captures : ignoré (canSave false)',
      build: () => LimitsAltBloc(
        api: _apiWith((_) {
          fail('PUT ne doit pas être appelé');
        }),
      ),
      act: (bloc) async {
        bloc.add(const LimitsAltSaveRequested());
        await Future<void>.delayed(const Duration(milliseconds: 30));
      },
      verify: (bloc) {
        expect(bloc.state.isSaved, isFalse);
        expect(bloc.state.isSaving, isFalse);
      },
    );
  });
}
