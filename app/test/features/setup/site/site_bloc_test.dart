import 'package:astro_brain/features/alignment/phone_location.dart';
import 'package:astro_brain/features/setup/site/site_bloc.dart';
import 'package:astro_brain/features/setup/site/site_event.dart';
import 'package:astro_brain/features/setup/site/site_repository.dart';
import 'package:astro_brain/features/setup/site/site_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements SiteRepository {}

/// Fake déterministe : ni plugin `geolocator`, ni permission à négocier.
class _FakePhoneLocation implements PhoneLocation {
  const _FakePhoneLocation(this.result);

  final ({double lat, double lon})? result;

  @override
  Future<({double lat, double lon})?> current() async => result;
}

final _site = ObservingSite(
  lat: 43.6045,
  lon: 1.4442,
  setAt: DateTime.utc(2026, 8, 26, 20),
);

void main() {
  late _MockRepo repo;

  setUp(() => repo = _MockRepo());

  blocTest<SiteBloc, SiteState>(
    'SiteLoaded — site connu → ready avec les coordonnées',
    build: () {
      when(() => repo.getSite()).thenAnswer((_) async => _site);
      return SiteBloc(repo: repo);
    },
    act: (b) => b.add(const SiteLoaded()),
    expect: () => [
      const SiteState(),
      isA<SiteState>()
          .having((s) => s.status, 'status', SiteStatus.ready)
          .having((s) => s.site?.lat, 'lat', 43.6045),
    ],
  );

  blocTest<SiteBloc, SiteState>(
    'SiteLoaded — aucun site → ready avec site null (état nominal)',
    build: () {
      when(() => repo.getSite()).thenAnswer((_) async => null);
      return SiteBloc(repo: repo);
    },
    act: (b) => b.add(const SiteLoaded()),
    expect: () => [
      const SiteState(),
      isA<SiteState>()
          .having((s) => s.status, 'status', SiteStatus.ready)
          .having((s) => s.site, 'site', isNull),
    ],
  );

  blocTest<SiteBloc, SiteState>(
    'SiteLoaded — GET en erreur → error, pas de crash',
    build: () {
      when(() => repo.getSite())
          .thenThrow(ApiException('boom', statusCode: 500));
      return SiteBloc(repo: repo);
    },
    act: (b) => b.add(const SiteLoaded()),
    expect: () => [
      const SiteState(),
      isA<SiteState>().having((s) => s.status, 'status', SiteStatus.error),
    ],
  );

  blocTest<SiteBloc, SiteState>(
    'SiteFromPhoneRequested — écrit la position du téléphone puis relit',
    build: () {
      when(() => repo.putSite(any(), any())).thenAnswer((_) async {});
      when(() => repo.getSite()).thenAnswer((_) async => _site);
      return SiteBloc(
        repo: repo,
        phoneLocation: const _FakePhoneLocation((lat: 43.6045, lon: 1.4442)),
      );
    },
    act: (b) => b.add(const SiteFromPhoneRequested()),
    expect: () => [
      isA<SiteState>().having((s) => s.status, 'status', SiteStatus.saving),
      isA<SiteState>()
          .having((s) => s.status, 'status', SiteStatus.ready)
          .having((s) => s.site?.lon, 'lon', 1.4442),
    ],
    verify: (_) {
      verify(() => repo.putSite(43.6045, 1.4442)).called(1);
    },
  );

  blocTest<SiteBloc, SiteState>(
    'SiteFromPhoneRequested — position refusée → error sans écriture',
    build: () {
      when(() => repo.putSite(any(), any())).thenAnswer((_) async {});
      return SiteBloc(
        repo: repo,
        phoneLocation: const _FakePhoneLocation(null),
      );
    },
    act: (b) => b.add(const SiteFromPhoneRequested()),
    expect: () => [
      isA<SiteState>().having((s) => s.status, 'status', SiteStatus.saving),
      isA<SiteState>()
          .having((s) => s.status, 'status', SiteStatus.error)
          .having((s) => s.error, 'error', contains('Position indisponible')),
    ],
    verify: (_) {
      // Ne jamais écrire un site faux : la garde ΔGPS du backend
      // invaliderait l'alignement en cours.
      verifyNever(() => repo.putSite(any(), any()));
    },
  );
}
