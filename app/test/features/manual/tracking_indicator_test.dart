import 'dart:convert';

import 'package:astro_brain/features/manual/widgets/tracking_indicator.dart';
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

SystemState _system(String mount, String tracking) =>
    SystemState.fromJson(jsonDecode('''
{
  "overall":"green",
  "subsystems":{
    "mount":{"state":"$mount","details":{},"since":"2026-01-01T00:00:00Z","message":null},
    "tracking":{"state":"$tracking","details":{},"since":"2026-01-01T00:00:00Z","message":null},
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
          child: const TrackingIndicator(),
        ),
      ),
    );

void main() {
  testWidgets('affiche SIDEREAL quand la monture suit', (tester) async {
    final bloc = _MockAppBloc();
    when(() => bloc.state).thenReturn(AppState(
      connection: ConnectionStatus.connected,
      system: _system('ready', 'sidereal'),
    ));

    await tester.pumpWidget(_host(bloc));

    expect(find.text('TRACKING SIDEREAL'), findsOneWidget);
  });

  testWidgets('affiche OFF + la façon de l\'armer quand il ne suit pas',
      (tester) async {
    final bloc = _MockAppBloc();
    when(() => bloc.state).thenReturn(AppState(
      connection: ConnectionStatus.connected,
      system: _system('ready', 'off'),
    ));

    await tester.pumpWidget(_host(bloc));

    expect(find.text('TRACKING OFF'), findsOneWidget);
    // Le switch est parti : sans cette phrase, « OFF » se lit comme une panne
    // alors que c'est l'état normal avant la première étoile.
    expect(find.textContaining('1ʳᵉ étoile'), findsOneWidget);
  });

  testWidgets('état inconnu (pas juste « off ») quand la monture est absente',
      (tester) async {
    final bloc = _MockAppBloc();
    when(() => bloc.state).thenReturn(AppState(
      connection: ConnectionStatus.connected,
      system: _system('disconnected', 'off'),
    ));

    await tester.pumpWidget(_host(bloc));

    expect(find.text('TRACKING —'), findsOneWidget);
    expect(find.text('TRACKING OFF'), findsNothing);
  });

  testWidgets('aucune commande exposée : plus de Switch', (tester) async {
    final bloc = _MockAppBloc();
    when(() => bloc.state).thenReturn(AppState(
      connection: ConnectionStatus.connected,
      system: _system('ready', 'sidereal'),
    ));

    await tester.pumpWidget(_host(bloc));

    expect(find.byType(Switch), findsNothing);
  });
}
