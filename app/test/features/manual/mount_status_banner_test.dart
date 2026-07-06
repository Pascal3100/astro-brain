import 'dart:convert';

import 'package:astro_brain/features/manual/widgets/mount_status_banner.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

class _MockAppBloc extends MockBloc<AppEvent, AppState> implements AppBloc {}

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

Widget _host(AppBloc bloc) => MaterialApp(
      theme: _theme(),
      home: Scaffold(
        body: BlocProvider<AppBloc>.value(
          value: bloc,
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
}
