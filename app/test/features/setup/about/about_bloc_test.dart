import 'package:astro_brain/features/setup/about/about_bloc.dart';
import 'package:astro_brain/features/setup/about/about_event.dart';
import 'package:astro_brain/features/setup/about/about_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/pi_host.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

ApiService _apiWith(MockClientHandler handler) =>
    ApiService(host: const PiHost(), client: MockClient(handler));

const _happyJson = '''
{
  "backend_version": "0.2.0",
  "app_version_seen": null,
  "mount_firmware": null,
  "ip": "192.168.1.42",
  "ssid": "fake-wifi",
  "uptime_s": 12345,
  "started_at": "2026-05-04T20:00:00+00:00"
}
''';

void main() {
  group('AboutBloc — AboutLoaded', () {
    blocTest<AboutBloc, AboutState>(
      'happy path → info rempli, isLoading=false, errorMessage=null',
      build: () => AboutBloc(
        api: _apiWith((req) async => http.Response(_happyJson, 200)),
      ),
      act: (bloc) => bloc.add(const AboutLoaded()),
      verify: (bloc) {
        expect(bloc.state.isLoading, isFalse);
        expect(bloc.state.errorMessage, isNull);
        expect(bloc.state.info, isNotNull);
        expect(bloc.state.info!.backendVersion, '0.2.0');
        expect(bloc.state.info!.ip, '192.168.1.42');
        expect(bloc.state.info!.ssid, 'fake-wifi');
        expect(bloc.state.info!.uptimeS, 12345);
        expect(bloc.state.info!.mountFirmware, isNull);
        expect(bloc.state.info!.appVersionSeen, isNull);
      },
    );

    blocTest<AboutBloc, AboutState>(
      '500 → errorMessage non null, info=null',
      build: () => AboutBloc(
        api: _apiWith(
          (req) async => http.Response('{"detail": "internal error"}', 500),
        ),
      ),
      act: (bloc) => bloc.add(const AboutLoaded()),
      verify: (bloc) {
        expect(bloc.state.isLoading, isFalse);
        expect(bloc.state.errorMessage, isNotNull);
        expect(bloc.state.info, isNull);
      },
    );
  });

  group('AboutBloc — AboutRefreshRequested', () {
    blocTest<AboutBloc, AboutState>(
      'refresh après erreur → récupère si backend répond 200',
      build: () {
        int calls = 0;
        return AboutBloc(
          api: _apiWith((req) async {
            calls++;
            if (calls == 1) {
              return http.Response('{"detail": "error"}', 500);
            }
            return http.Response(_happyJson, 200);
          }),
        );
      },
      act: (bloc) async {
        bloc.add(const AboutLoaded());
        await Future<void>.delayed(const Duration(milliseconds: 30));
        expect(bloc.state.errorMessage, isNotNull);
        bloc.add(const AboutRefreshRequested());
      },
      verify: (bloc) {
        expect(bloc.state.isLoading, isFalse);
        expect(bloc.state.errorMessage, isNull);
        expect(bloc.state.info, isNotNull);
        expect(bloc.state.info!.backendVersion, '0.2.0');
      },
    );
  });
}
