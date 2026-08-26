import 'package:astro_brain/features/alignment/alignment_bloc.dart';
import 'package:astro_brain/features/alignment/alignment_event.dart';
import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
import 'package:astro_brain/features/alignment/alignment_state.dart';
import 'package:astro_brain/features/alignment/phone_location.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements AlignmentRepository {}

class _MockPhoneLocation extends Mock implements PhoneLocation {}

/// Fake qui retourne toujours une position fixe.
class _FakePhoneLocation implements PhoneLocation {
  _FakePhoneLocation({required this.result});
  final ({double lat, double lon})? result;
  @override
  Future<({double lat, double lon})?> current() async => result;
}

AlignmentSessionDto _sessionWithIdx(int idx, {int recCount = 0}) =>
    AlignmentSessionDto(
      sessionId: 's1',
      candidates: List.generate(
        3,
        (i) => StarDto(
          id: 'x$i',
          name: 'X$i',
          bayer: '-',
          raDeg: i * 100.0,
          decDeg: 10,
          mag: 1,
        ),
      ),
      recordedStars: List.generate(
        recCount,
        (i) => StarRecordDto(
          starId: 'x$i',
          skyAz: 0,
          skyAlt: 0,
          mountAz: 0,
          mountAlt: 0,
        ),
      ),
      currentIdx: idx,
    );

void main() {
  late _MockRepo repo;
  setUp(() => repo = _MockRepo());

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted → LoadingCandidates → PrePointing(idx=0)',
    build: () {
      when(() => repo.getSession()).thenAnswer((_) async => null);
      when(() => repo.start()).thenAnswer((_) async => _sessionWithIdx(0));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 0),
    ],
    verify: (_) {
      verify(() => repo.getSession()).called(1);
      verify(() => repo.start()).called(1);
    },
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted resumes existing session if backend already has one',
    build: () {
      when(
        () => repo.getSession(),
      ).thenAnswer((_) async => _sessionWithIdx(2, recCount: 2));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 2),
    ],
    verify: (_) {
      verify(() => repo.getSession()).called(1);
      verifyNever(() => repo.start());
    },
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RecordRequested → next star',
    build: () {
      when(
        () => repo.record(0),
      ).thenAnswer((_) async => _sessionWithIdx(1, recCount: 1));
      return AlignmentBloc(repo: repo);
    },
    seed: () => AlignmentFineTuning(session: _sessionWithIdx(0)),
    act: (b) => b.add(const RecordRequested(0)),
    expect: () => [
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 1),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RecordRequested last → Validating with model',
    build: () {
      when(
        () => repo.record(2),
      ).thenAnswer((_) async => _sessionWithIdx(3, recCount: 3));
      when(() => repo.finalize()).thenAnswer(
        (_) async => AlignmentModelDto(
          recordedStars: const [],
          rmsArcmin: 5.4,
          residuals: const {'x0': 2.1, 'x1': 11.4, 'x2': 2.8},
          validatedAtUtc: '2026-05-09T22:00:00+00:00',
          quality: 'good',
        ),
      );
      return AlignmentBloc(repo: repo);
    },
    seed: () => AlignmentFineTuning(session: _sessionWithIdx(2, recCount: 2)),
    act: (b) => b.add(const RecordRequested(2)),
    expect: () => [
      isA<AlignmentValidating>()
          .having((s) => s.model.outlierId, 'outlier', 'x1')
          .having((s) => s.candidates.length, 'candidates', 3),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'RestartStarRequested truncates and goes to PrePointing',
    build: () {
      when(
        () => repo.restartStar(1),
      ).thenAnswer((_) async => _sessionWithIdx(1, recCount: 1));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const RestartStarRequested(1)),
    expect: () => [
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 1),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardCancelled clears session',
    build: () {
      when(() => repo.cancel()).thenAnswer((_) async {});
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardCancelled()),
    expect: () => [isA<AlignmentIdle>()],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted → AlignmentError when repo throws',
    build: () {
      when(() => repo.getSession()).thenThrow(Exception('boom'));
      return AlignmentBloc(repo: repo);
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentError>().having((s) => s.message, 'msg', contains('boom')),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'PrePointingDone → FineTuning (same session)',
    build: () => AlignmentBloc(repo: repo),
    seed: () => AlignmentPrePointing(session: _sessionWithIdx(0)),
    act: (b) => b.add(const PrePointingDone()),
    expect: () => [
      isA<AlignmentFineTuning>().having((s) => s.session.currentIdx, 'idx', 0),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'MountDisconnected → AlignmentError',
    build: () => AlignmentBloc(repo: repo),
    act: (b) => b.add(const MountDisconnected()),
    expect: () => [
      isA<AlignmentError>().having(
        (s) => s.message,
        'msg',
        'Monture déconnectée',
      ),
    ],
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'ValidationAccepted → AlignmentDone',
    build: () => AlignmentBloc(repo: repo),
    act: (b) => b.add(const ValidationAccepted()),
    expect: () => [isA<AlignmentDone>()],
  );

  // ---------------------------------------------------------------------------
  // Fallback GPS téléphone
  // ---------------------------------------------------------------------------

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted — 409 puis GPS téléphone disponible → putSite + start → PrePointing',
    build: () {
      when(() => repo.getSession()).thenAnswer((_) async => null);

      // Premier appel → 409 (pas de position Pi).
      var startCalls = 0;
      when(() => repo.start()).thenAnswer((_) async {
        startCalls++;
        if (startCalls == 1) {
          throw ApiException('position requise', statusCode: 409);
        }
        return _sessionWithIdx(0);
      });

      when(
        () => repo.putSite(43.6, 1.44),
      ).thenAnswer((_) async {});

      return AlignmentBloc(
        repo: repo,
        phoneLocation: _FakePhoneLocation(result: (lat: 43.6, lon: 1.44)),
      );
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentPrePointing>().having((s) => s.session.currentIdx, 'idx', 0),
    ],
    verify: (_) {
      verify(() => repo.putSite(43.6, 1.44)).called(1);
      verify(() => repo.start()).called(2);
    },
  );

  blocTest<AlignmentBloc, AlignmentState>(
    'WizardStarted — 409 et GPS téléphone refusé → AlignmentError position requise',
    build: () {
      when(() => repo.getSession()).thenAnswer((_) async => null);
      when(
        () => repo.start(),
      ).thenThrow(ApiException('position requise', statusCode: 409));

      return AlignmentBloc(
        repo: repo,
        phoneLocation: _FakePhoneLocation(result: null), // permission refusée
      );
    },
    act: (b) => b.add(const WizardStarted()),
    expect: () => [
      isA<AlignmentLoadingCandidates>(),
      isA<AlignmentError>().having(
        (s) => s.message,
        'msg',
        contains('Position GPS requise'),
      ),
    ],
    verify: (_) {
      verifyNever(() => repo.putSite(any(), any()));
    },
  );

  () {
    final phoneLoc = _MockPhoneLocation();
    blocTest<AlignmentBloc, AlignmentState>(
      'WizardStarted — erreur non-409 n\'active pas le fallback GPS',
      build: () {
        when(() => repo.getSession()).thenAnswer((_) async => null);
        when(
          () => repo.start(),
        ).thenThrow(ApiException('server error', statusCode: 500));

        return AlignmentBloc(repo: repo, phoneLocation: phoneLoc);
      },
      act: (b) => b.add(const WizardStarted()),
      expect: () => [
        isA<AlignmentLoadingCandidates>(),
        isA<AlignmentError>().having(
          (s) => s.message,
          'msg',
          contains('server error'),
        ),
      ],
      // _MockPhoneLocation.current() n'a pas été appelé.
      verify: (_) {
        verifyNever(() => repo.putSite(any(), any()));
        verifyNever(() => phoneLoc.current());
      },
    );
  }();
}
