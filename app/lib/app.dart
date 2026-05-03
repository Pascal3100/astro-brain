import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'features/home/home_bloc.dart';
import 'features/home/home_screen.dart';
import 'features/splash/splash_cubit.dart';
import 'features/splash/splash_screen.dart';
import 'services/api_service.dart';
import 'services/event_stream_service.dart';
import 'services/pi_host.dart';
import 'state/app_bloc/app_bloc.dart';
import 'theme/astro_theme.dart';
import 'theme/theme_cubit.dart';

class AstroBrainApp extends StatelessWidget {
  const AstroBrainApp({super.key, required this.prefs, required this.host});

  final SharedPreferences prefs;
  final PiHost host;

  @override
  Widget build(BuildContext context) {

    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider<PiHost>.value(value: host),
        RepositoryProvider<ApiService>(
          create: (_) => ApiService(host: host),
          dispose: (s) => s.dispose(),
        ),
        RepositoryProvider<EventStreamService>(
          create: (_) => EventStreamService(host: host),
          dispose: (s) => s.dispose(),
        ),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider<ThemeCubit>(create: (_) => ThemeCubit(prefs: prefs)),
          BlocProvider<AppBloc>(
            create: (ctx) => AppBloc(
              eventStream: ctx.read<EventStreamService>(),
            ),
          ),
          BlocProvider<HomeBloc>(
            create: (ctx) => HomeBloc(api: ctx.read<ApiService>()),
          ),
        ],
        child: BlocBuilder<ThemeCubit, AstroThemeMode>(
          builder: (ctx, mode) {
            return MaterialApp(
              title: 'Astro-Brain',
              debugShowCheckedModeBanner: false,
              theme: AstroTheme.buildDay(),
              darkTheme: AstroTheme.buildNight(),
              themeMode: mode == AstroThemeMode.day
                  ? ThemeMode.light
                  : ThemeMode.dark,
              home: _RootRouter(),
            );
          },
        ),
      ),
    );
  }
}

class _RootRouter extends StatefulWidget {
  @override
  State<_RootRouter> createState() => _RootRouterState();
}

class _RootRouterState extends State<_RootRouter> {
  bool _ready = false;

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return BlocProvider<SplashCubit>(
        create: (ctx) => SplashCubit(
          api: ctx.read<ApiService>(),
          appBloc: ctx.read<AppBloc>(),
        ),
        child: SplashScreen(onReady: () => setState(() => _ready = true)),
      );
    }
    return const HomeScreen();
  }
}
