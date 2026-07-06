import 'dart:convert';

import 'package:astro_brain/features/manual/manual_bloc.dart';
import 'package:astro_brain/features/manual/widgets/mount_status_banner.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockAppBloc extends MockBloc<AppEvent, AppState> implements AppBloc {}

class _MockManualBloc extends MockBloc<ManualEvent, ManualState>
    implements ManualBloc {}

SystemState _systemWithMount(String state, {String? message}) =>
    SystemState.fromJson(jsonDecode('''
{
  "overall":"orange",
  "subsystems":{
    "mount":{"state":"$state","details":{},"since":"2026-01-01T00:00:00Z","message":${message == null ? 'null' : '"$message"'}},
    "gps":{"state":"no_fix","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "tracking":{"state":"off","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "network":{"state":"client","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "system":{"state":"ok","details":{},"since":"2026-01-01T00:00:00Z","message":null}
  },
  "seq":1,"ts":"2026-01-01T00:00:00Z"
}
''') as Map<String, dynamic>);

ThemeData _theme() => ThemeData(
      extensions: <ThemeExtension<dynamic>>[
        AppColors.day,
        const AppTextStyles(
          hudLabel: TextStyle(),
          hudValue: TextStyle(),
          hudCaption: TextStyle(),
          hudBadge: TextStyle(),
        ),
      ],
    );

Widget _host(AppBloc bloc, {ManualBloc? manual}) => MaterialApp(
      theme: _theme(),
      home: Scaffold(
        body: MultiBlocProvider(
          providers: [
            BlocProvider<AppBloc>.value(value: bloc),
            if (manual != null) BlocProvider<ManualBloc>.value(value: manual),
          ],
          child: const MountStatusBanner(),
        ),
      ),
    );

void main() {
  testWidgets('bannière visible + message quand mount == error', (tester) async {
    final bloc = _MockAppBloc();
    whenListen(
      bloc,
      const Stream<AppState>.empty(),
      initialState: AppState(
        connection: ConnectionStatus.connected,
        system: _systemWithMount('error', message: 'TELESCOPE_SLEW_RATE absent'),
      ),
    );

    await tester.pumpWidget(_host(bloc));

    expect(find.byKey(const Key('mount-status-banner')), findsOneWidget);
    expect(find.textContaining('TELESCOPE_SLEW_RATE absent'), findsOneWidget);
  });

  testWidgets('bannière visible quand mount == disconnected', (tester) async {
    final bloc = _MockAppBloc();
    whenListen(
      bloc,
      const Stream<AppState>.empty(),
      initialState: AppState(
        connection: ConnectionStatus.connected,
        system: _systemWithMount('disconnected'),
      ),
    );

    await tester.pumpWidget(_host(bloc));

    expect(find.byKey(const Key('mount-status-banner')), findsOneWidget);
    expect(find.textContaining('déconnectée'), findsOneWidget);
  });

  testWidgets('rien quand mount == ready', (tester) async {
    final bloc = _MockAppBloc();
    whenListen(
      bloc,
      const Stream<AppState>.empty(),
      initialState: AppState(
        connection: ConnectionStatus.connected,
        system: _systemWithMount('ready'),
      ),
    );

    await tester.pumpWidget(_host(bloc));

    expect(find.byKey(const Key('mount-status-banner')), findsNothing);
  });

  testWidgets('bouton RECONNECTER dispatch ManualReconnectPressed',
      (tester) async {
    final bloc = _MockAppBloc();
    whenListen(
      bloc,
      const Stream<AppState>.empty(),
      initialState: AppState(
        connection: ConnectionStatus.connected,
        system: _systemWithMount('disconnected'),
      ),
    );
    final manual = _MockManualBloc();
    whenListen(
      manual,
      const Stream<ManualState>.empty(),
      initialState: const ManualState(),
    );

    await tester.pumpWidget(_host(bloc, manual: manual));
    await tester.tap(find.byKey(const Key('mount-reconnect-button')));
    await tester.pump(const Duration(milliseconds: 350)); // settle ripple

    verify(() => manual.add(const ManualReconnectPressed())).called(1);
  });
}
